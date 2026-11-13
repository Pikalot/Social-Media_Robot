import hashlib

from ai import is_same_complaint, summarize
from monitors.base import Review

LOW_RATING_THRESHOLD = 3
CLOSED_STATUSES = ("Done", "Closed")  # final: never changed again


def _review_hash(review: Review) -> str:
    # One review per author per business per platform. Text and date are left
    # out on purpose so an edited review is still treated as the same review.
    # Must stay in sync with the SQL in db.migrate_review_hashes().
    raw = f"{review.business}|{review.platform}|{review.author}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _set_status(cursor, report_id: int, status: str) -> None:
    """Change only the status; flag the row so generate_report.py updates Excel."""
    cursor.execute(
        "UPDATE reports SET status = %s, synced = 0 WHERE id = %s AND status <> %s",
        (status, report_id, status),
    )


def _flag_date_change(cursor, report_id: int) -> None:
    """The review's date changed; flag the row so Excel gets the new date."""
    cursor.execute("UPDATE reports SET synced = 0 WHERE id = %s", (report_id,))


def _create_report(cursor, review_id: int, review: Review, branch_codes: dict[str, str]) -> None:
    branch_code = branch_codes.get(review.business, review.business)
    cursor.execute(
        """
        INSERT INTO reports (review_id, branch_code, status, description)
        VALUES (%s, %s, 'Open', %s)
        """,
        (review_id, branch_code, summarize(review.text)[:512]),
    )


def sync_reviews(
    conn,
    reviews: list[Review],
    branch_codes: dict[str, str],
    complete: set[tuple[str, str]] = frozenset(),
) -> list[Review]:
    """Bring the DB in line with what the platform currently shows.
    Nothing is ever deleted, and a report's description is never changed
    after it is created (it keeps the original complaint wording).

    - New review, rating <= threshold   -> new 'Open' report.
    - Rating rises above threshold      -> report status 'Done' (only change).
    - Report is Done/Closed             -> never changed again. If the rating
                                           is <= threshold and the date changed,
                                           it is a new complaint -> new report.
    - Edited, still <= threshold, same  -> Excel date updated if the review
      meaning (Claude decides)             date changed; otherwise untouched.
    - Edited, still <= threshold, the   -> old report 'Done', new report for
      meaning changed                      the new complaint (new Excel row).
    - Reviewer deleted the review       -> report status 'Done' (only change).
      Only checked for (business, platform) pairs in `complete`, i.e. where
      the platform returned every review; otherwise a missing review may just
      be outside the window (Google's API returns at most 5 reviews per place).

    Returns the reviews that were new.
    """
    cursor = conn.cursor()
    new_reviews = []
    seen_hashes: dict[tuple[str, str], set[str]] = {}

    for review in reviews:
        review_hash = _review_hash(review)
        seen_hashes.setdefault((review.business, review.platform), set()).add(review_hash)

        cursor.execute(
            "SELECT id, rating, text, review_time FROM reviews WHERE review_hash = %s",
            (review_hash,),
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                """
                INSERT INTO reviews
                    (business, author, rating, text, review_time, platform, link, review_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (review.business, review.author, review.rating, review.text,
                 review.time, review.platform, review.link, review_hash),
            )
            new_reviews.append(review)
            if review.rating <= LOW_RATING_THRESHOLD:
                _create_report(cursor, cursor.lastrowid, review, branch_codes)
            continue

        review_id, old_rating, old_text, old_time = row
        if (old_rating, old_text or "", old_time or "") == (review.rating, review.text, review.time):
            continue  # unchanged

        # Keep the DB's copy of the review current so the next scan compares
        # against the latest version. The report's description is not touched.
        cursor.execute(
            "UPDATE reviews SET rating = %s, text = %s, review_time = %s WHERE id = %s",
            (review.rating, review.text, review.time, review_id),
        )

        cursor.execute(
            "SELECT id, status FROM reports WHERE review_id = %s ORDER BY id DESC LIMIT 1",
            (review_id,),
        )
        report = cursor.fetchone()
        low = review.rating <= LOW_RATING_THRESHOLD

        if report is None:
            if low:
                _create_report(cursor, review_id, review, branch_codes)
            continue

        report_id, status = report
        date_changed = (old_time or "") != review.time

        if status in CLOSED_STATUSES:
            # Done is final: never reopen or edit it. A low rating with a new
            # date is a new complaint -> new report (new Excel row).
            dropped_back = old_rating > LOW_RATING_THRESHOLD
            if low and date_changed and (dropped_back or not is_same_complaint(old_text, review.text)):
                print(f"[{review.platform}] {review.author} new complaint ({review.rating}★) after closed report {report_id}")
                _create_report(cursor, review_id, review, branch_codes)
            continue

        if not low:
            print(f"[{review.platform}] {review.author} raised to {review.rating}★; report {report_id} -> Done")
            _set_status(cursor, report_id, "Done")
        elif (old_text or "") != review.text and not is_same_complaint(old_text, review.text):
            # Meaning changed: close the old complaint, log the new one.
            print(f"[{review.platform}] {review.author} changed the complaint; report {report_id} -> Done, new report")
            _set_status(cursor, report_id, "Done")
            _create_report(cursor, review_id, review, branch_codes)
        elif date_changed:
            _flag_date_change(cursor, report_id)  # same complaint, new date

    # Reviews the reviewer deleted -> mark their reports Done (rows are kept).
    for business, platform in complete:
        _resolve_removed(cursor, business, platform, seen_hashes.get((business, platform), set()))

    conn.commit()
    cursor.close()
    return new_reviews


def _resolve_removed(cursor, business: str, platform: str, present_hashes: set[str]) -> None:
    cursor.execute(
        """
        SELECT rp.id, rv.review_hash
        FROM reports rp JOIN reviews rv ON rv.id = rp.review_id
        WHERE rv.business = %s AND rv.platform = %s AND rp.status NOT IN ('Done', 'Closed')
        """,
        (business, platform),
    )
    for report_id, review_hash in cursor.fetchall():
        if review_hash not in present_hashes:
            print(f"[{platform}] Review deleted by reviewer at {business}; report {report_id} -> Done")
            _set_status(cursor, report_id, "Done")
