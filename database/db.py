import sqlite3
from typing import List, Tuple, Optional

class ReviewDB:


    def __init__(self, db_path: str = "reviews.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    review TEXT NOT NULL,
                    answered INTEGER DEFAULT 0,
                    admin_answer TEXT DEFAULT NULL
                )
            ''')


    def add_review(self, user_id: int, username: Optional[str], review: str) -> int:
        """Добавить отзыв, возвращает id добавленной записи"""
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO reviews (user_id, username, review) VALUES (?, ?, ?)",
                (user_id, username, review)
            )
            return cursor.lastrowid


    def get_unanswered_reviews(self) -> List[Tuple[int, int, Optional[str], str]]:
        """Получить список необработанных отзывов (id, user_id, username, review)"""
        cursor = self.conn.execute(
            "SELECT id, user_id, username, review FROM reviews WHERE answered = 0"
        )
        return cursor.fetchall()


    def mark_review_answered(self, review_id: int, answer_text: str) -> None:
        """Пометить отзыв как отвеченный"""
        with self.conn:
            self.conn.execute(
                "UPDATE reviews SET answered = 1, admin_answer = ? WHERE id = ?",
                (answer_text, review_id)
                )

    
    def get_answered_reviews(self) -> List[Tuple[int, int, Optional[str], str, Optional[str]]]:
        """Получить список обработанных отзывов (id, user_id, username, review, admin_answer)"""
        cursor = self.conn.execute(
            "SELECT id, user_id, username, review, admin_answer FROM reviews WHERE answered = 1"
            )
        return cursor.fetchall()
    

    def count_users(self) -> int:
        """Возвращает количество уникальных пользователей, которые воспользовались ботом (например, оставили отзывы)."""
        cursor = self.conn.execute("SELECT COUNT(DISTINCT user_id) FROM reviews")
        result = cursor.fetchone()
        return result[0] if result else 0

    def count_reviews(self) -> int:
        """Возвращает общее количество отзывов."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM reviews")
        result = cursor.fetchone()
        return result[0] if result else 0


    def close(self):
        self.conn.close()
