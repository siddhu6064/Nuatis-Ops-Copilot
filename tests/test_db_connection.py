import unittest

from db.connection import connect, disconnect


class DatabaseConnectionTests(unittest.TestCase):
    def test_sqlite_memory_connects_and_disconnects(self) -> None:
        db = connect("sqlite:///:memory:")
        self.assertEqual(db.backend, "sqlite")

        cursor = db.connection.cursor()
        cursor.execute("SELECT 1")
        self.assertEqual(cursor.fetchone()[0], 1)

        disconnect(db)

    def test_invalid_scheme_raises(self) -> None:
        with self.assertRaises(ValueError):
            connect("mysql://localhost/demo")


if __name__ == "__main__":
    unittest.main()
