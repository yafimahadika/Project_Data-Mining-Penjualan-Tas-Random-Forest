import mysql.connector
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=current_app.config["DB_HOST"],
            port=current_app.config["DB_PORT"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],
        )
    return g.db


def query(sql, params=None, fetchone=False, commit=False):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql, params or ())

    result = None
    if commit:
        conn.commit()
    elif fetchone:
        result = cursor.fetchone()
    else:
        result = cursor.fetchall()

    cursor.close()
    return result


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
