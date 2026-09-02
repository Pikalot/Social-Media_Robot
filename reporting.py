import hashlib

from monitors.base import Review

LOW_RATING_THRESHOLD = 3


def _review_hash(review: Review) -> str:
    raw = f"{review.business}|{review.author}|{review.time}|{review.text}"
    return hashlib.sha256(raw.encode()).hexdigest()


def save_new_reviews(conn, reviews: list[Review], branch_codes: dict[str, str]) -> list[Review]:
    """Insert reviews the DB hasn't seen before, and file a report for any
    new review at or below LOW_RATING_THRESHOLD. Returns the reviews that
    were actually new."""
    cursor = conn.cursor()
    new_reviews = []
    for review in reviews:
        review_hash = _review_hash(review)
        cursor.execute(
            """
            INSERT IGNORE INTO reviews
                (business, author, rating, text, review_time, platform, link, review_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                review.business,
                review.author,
                review.rating,
                review.text,
                review.time,
                review.platform,
                review.link,
                review_hash,
            ),
        )
        if cursor.rowcount == 0:
            continue  # already existed

        new_reviews.append(review)
        review_id = cursor.lastrowid

        if review.rating <= LOW_RATING_THRESHOLD:
            branch_code = branch_codes.get(review.business, review.business)
            description = f"{review.rating}★ {review.platform} review by {review.author}: {review.text[:150]}"
            cursor.execute(
                """
                INSERT INTO reports (review_id, branch_code, status, description)
                VALUES (%s, %s, 'Open', %s)
                """,
                (review_id, branch_code, description),
            )

    conn.commit()
    cursor.close()
    return new_reviews
