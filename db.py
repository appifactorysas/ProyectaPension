# -*- coding: utf-8 -*-
"""Gestión de usuarios y conteo de uso — SQLite."""
import logging
import os
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

HASH_METHOD = 'pbkdf2:sha256'

DB_PATH = os.environ.get('DB_PATH', os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'data', 'proyectapension.db'))

log = logging.getLogger(__name__)


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    UNIQUE NOT NULL COLLATE NOCASE,
            password_hash TEXT  NOT NULL,
            nombre      TEXT    DEFAULT '',
            email       TEXT    DEFAULT '',
            is_admin    INTEGER DEFAULT 0,
            is_active   INTEGER DEFAULT 1,
            max_consultas INTEGER DEFAULT 0,
            created_at  TEXT    DEFAULT (datetime('now')),
            updated_at  TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS uso (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id  INTEGER NOT NULL,
            tipo        TEXT    DEFAULT 'consulta',
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );
        CREATE INDEX IF NOT EXISTS idx_uso_usuario ON uso(usuario_id);
        CREATE INDEX IF NOT EXISTS idx_uso_fecha   ON uso(created_at);
    """)
    conn.commit()
    conn.close()


def crear_admin_inicial(username, password):
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if count == 0:
        try:
            conn.execute(
                "INSERT INTO usuarios "
                "(username, password_hash, nombre, is_admin, max_consultas) "
                "VALUES (?, ?, 'Administrador', 1, 0)",
                (username, generate_password_hash(password, method=HASH_METHOD)),
            )
            conn.commit()
            log.info("Usuario admin '%s' creado.", username)
        except sqlite3.IntegrityError:
            pass
    conn.close()


# ── Autenticación ────────────────────────────────────────────────────

def autenticar(username, password):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE username = ? AND is_active = 1",
        (username,),
    ).fetchone()
    conn.close()
    if row and check_password_hash(row['password_hash'], password):
        return dict(row)
    return None


# ── CRUD de usuarios ─────────────────────────────────────────────────

def get_usuario(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def listar_usuarios():
    conn = get_db()
    rows = conn.execute("""
        SELECT u.*, COALESCE(c.total, 0) AS consultas_usadas
        FROM usuarios u
        LEFT JOIN (
            SELECT usuario_id, COUNT(*) AS total FROM uso GROUP BY usuario_id
        ) c ON c.usuario_id = u.id
        ORDER BY u.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def crear_usuario(username, password, nombre='', email='',
                  is_admin=False, max_consultas=0):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO usuarios "
            "(username, password_hash, nombre, email, is_admin, max_consultas) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, generate_password_hash(password, method=HASH_METHOD),
             nombre, email, int(is_admin), max_consultas),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def actualizar_usuario(user_id, **kwargs):
    conn = get_db()
    sets, vals = [], []
    for k, v in kwargs.items():
        if k == 'password' and v:
            sets.append("password_hash = ?")
            vals.append(generate_password_hash(v, method=HASH_METHOD))
        elif k in ('username', 'nombre', 'email'):
            sets.append(f"{k} = ?")
            vals.append(v)
        elif k in ('is_admin', 'is_active', 'max_consultas'):
            sets.append(f"{k} = ?")
            vals.append(int(v))
    if not sets:
        conn.close()
        return True
    sets.append("updated_at = datetime('now')")
    vals.append(user_id)
    try:
        conn.execute(
            f"UPDATE usuarios SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    conn.close()
    return ok


def eliminar_usuario(user_id):
    conn = get_db()
    conn.execute("DELETE FROM uso WHERE usuario_id = ?", (user_id,))
    conn.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# ── Conteo de uso ────────────────────────────────────────────────────

def registrar_uso(usuario_id, tipo='consulta'):
    conn = get_db()
    conn.execute(
        "INSERT INTO uso (usuario_id, tipo) VALUES (?, ?)",
        (usuario_id, tipo),
    )
    conn.commit()
    conn.close()


def consultas_usadas(usuario_id):
    conn = get_db()
    n = conn.execute(
        "SELECT COUNT(*) FROM uso WHERE usuario_id = ?", (usuario_id,),
    ).fetchone()[0]
    conn.close()
    return n


def puede_consultar(usuario_id):
    user = get_usuario(usuario_id)
    if not user or not user['is_active']:
        return False
    if user['max_consultas'] <= 0:
        return True
    return consultas_usadas(usuario_id) < user['max_consultas']


def consultas_restantes(usuario_id):
    user = get_usuario(usuario_id)
    if not user:
        return 0
    if user['max_consultas'] <= 0:
        return -1
    return max(0, user['max_consultas'] - consultas_usadas(usuario_id))


# ── Estadísticas ─────────────────────────────────────────────────────

def stats_uso():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM uso").fetchone()[0]
    hoy = conn.execute(
        "SELECT COUNT(*) FROM uso WHERE date(created_at) = date('now')",
    ).fetchone()[0]
    mes = conn.execute(
        "SELECT COUNT(*) FROM uso "
        "WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')",
    ).fetchone()[0]
    total_usuarios = conn.execute(
        "SELECT COUNT(*) FROM usuarios",
    ).fetchone()[0]
    activos = conn.execute(
        "SELECT COUNT(*) FROM usuarios WHERE is_active = 1",
    ).fetchone()[0]
    log_entries = conn.execute("""
        SELECT uso.id, uso.tipo, uso.created_at, u.username, u.nombre
        FROM uso JOIN usuarios u ON u.id = uso.usuario_id
        ORDER BY uso.created_at DESC LIMIT 50
    """).fetchall()
    por_usuario = conn.execute("""
        SELECT u.id, u.username, u.nombre, u.max_consultas,
               COALESCE(c.total, 0) AS consultas_usadas
        FROM usuarios u
        LEFT JOIN (
            SELECT usuario_id, COUNT(*) AS total FROM uso GROUP BY usuario_id
        ) c ON c.usuario_id = u.id
        WHERE u.is_active = 1
        ORDER BY consultas_usadas DESC
    """).fetchall()
    diario = conn.execute("""
        SELECT date(created_at) AS dia, COUNT(*) AS total
        FROM uso WHERE created_at >= datetime('now', '-30 days')
        GROUP BY dia ORDER BY dia
    """).fetchall()
    conn.close()
    return {
        'total': total, 'hoy': hoy, 'mes': mes,
        'total_usuarios': total_usuarios, 'activos': activos,
        'log': [dict(r) for r in log_entries],
        'por_usuario': [dict(r) for r in por_usuario],
        'diario': [dict(r) for r in diario],
    }
