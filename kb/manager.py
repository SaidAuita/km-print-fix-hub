import os
import sqlite3
import json
import zipfile
import shutil
from datetime import datetime

class KBManager:
    def __init__(self, data_dir="kb_data"):
        self.data_dir = data_dir
        self.active_db_name = None
        self.active_db_path = None
        
        # Ensure directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "attachments"), exist_ok=True)
        self.backup_dir = os.path.join(os.path.dirname(self.data_dir) or ".", "Backup")
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Load last active database from general settings if exists
        self.load_last_active_db()

    def get_db_path(self, db_name):
        # Normalize and prevent directory traversal
        db_name = os.path.basename(db_name)
        if not db_name.endswith(".db"):
            db_name += ".db"
        return os.path.join(self.data_dir, db_name)

    def load_last_active_db(self):
        # We can store the active DB name in a small JSON file in data_dir
        active_info_path = os.path.join(self.data_dir, "active_db.json")
        if os.path.exists(active_info_path):
            try:
                with open(active_info_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    name = data.get("active_db")
                    if name:
                        self.active_db_name = os.path.basename(name)
                        if not self.active_db_name.endswith(".db"):
                            self.active_db_name += ".db"
                        self.active_db_path = self.get_db_path(self.active_db_name)
            except Exception:
                pass

    def save_last_active_db(self):
        active_info_path = os.path.join(self.data_dir, "active_db.json")
        try:
            with open(active_info_path, "w", encoding="utf-8") as f:
                json.dump({"active_db": self.active_db_name}, f)
        except Exception:
            pass

    def set_active_db(self, db_name):
        self.active_db_name = os.path.basename(db_name)
        if not self.active_db_name.endswith(".db"):
            self.active_db_name += ".db"
        self.active_db_path = self.get_db_path(self.active_db_name)
        self.save_last_active_db()
        # Initialize schema if new
        self.init_db_schema()

    def get_connection(self):
        if not self.active_db_path:
            raise Exception("No active database selected")
        conn = sqlite3.connect(self.active_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db_schema(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Enable WAL mode for concurrency and performance
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        # 1. Settings Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        
        # 2. Solutions Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS solutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            machine TEXT,
            serial_number TEXT,
            symptom TEXT,
            cause TEXT,
            solution TEXT,
            actions TEXT,
            result TEXT,
            date TEXT NOT NULL,
            author TEXT,
            tags TEXT, -- Comma-separated list
            forum_links TEXT, -- JSON array of strings
            manual_links TEXT, -- JSON array of strings
            photos TEXT, -- JSON array of filenames
            attachments TEXT -- JSON array of filenames
        );
        """)
        
        # 3. Maintenance History Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL, -- parts_replacement, preventive, cleaning, adjustment, firmware, repair, setup
            title TEXT, -- Unique descriptor for linking
            date TEXT NOT NULL,
            counter INTEGER,
            performer TEXT,
            comments TEXT,
            photos TEXT, -- JSON array of filenames
            cost REAL
        );
        """)
        
        # Check and alter schema for existing tables
        cursor.execute("PRAGMA table_info(maintenance_history)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "title" not in columns:
            cursor.execute("ALTER TABLE maintenance_history ADD COLUMN title TEXT")
        
        # 4. Installed Parts Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS installed_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_name TEXT NOT NULL,
            date_installed TEXT NOT NULL,
            date_removed TEXT,
            resource_limit INTEGER,
            current_counter INTEGER,
            comments TEXT
        );
        """)
        
        # 5. User Instructions Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_instructions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            date_created TEXT NOT NULL,
            tags TEXT -- Comma-separated list
        );
        """)
        
        # 6. Related Records Table (Graph relations)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS related_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type_a TEXT NOT NULL, -- solution, maintenance, part, instruction
            record_id_a INTEGER NOT NULL,
            record_type_b TEXT NOT NULL,
            record_id_b INTEGER NOT NULL,
            UNIQUE(record_type_a, record_id_a, record_type_b, record_id_b)
        );
        """)
        
        # 7. FTS5 Virtual Table for Instant Search
        cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_kb USING fts5(
            record_type,
            record_id UNINDEXED,
            title,
            content,
            tags,
            tokenize='porter unicode61'
        );
        """)
        
        # Create triggers to sync FTS5 virtual table automatically
        
        # Solutions Triggers
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_solutions_insert AFTER INSERT ON solutions BEGIN
            INSERT INTO fts_kb(record_type, record_id, title, content, tags)
            VALUES ('solution', new.id, new.title, 
                    coalesce(new.symptom, '') || ' ' || coalesce(new.cause, '') || ' ' || coalesce(new.solution, '') || ' ' || coalesce(new.actions, '') || ' ' || coalesce(new.result, ''), 
                    new.tags);
        END;
        """)
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_solutions_update AFTER UPDATE ON solutions BEGIN
            UPDATE fts_kb SET 
                title = new.title,
                content = coalesce(new.symptom, '') || ' ' || coalesce(new.cause, '') || ' ' || coalesce(new.solution, '') || ' ' || coalesce(new.actions, '') || ' ' || coalesce(new.result, ''),
                tags = new.tags
            WHERE record_type = 'solution' AND record_id = old.id;
        END;
        """)
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_solutions_delete AFTER DELETE ON solutions BEGIN
            DELETE FROM fts_kb WHERE record_type = 'solution' AND record_id = old.id;
        END;
        """)
        
        # Maintenance Triggers
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_maintenance_insert AFTER INSERT ON maintenance_history BEGIN
            INSERT INTO fts_kb(record_type, record_id, title, content, tags)
            VALUES ('maintenance', new.id, coalesce(new.title, new.type), new.comments, '');
        END;
        """)
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_maintenance_update AFTER UPDATE ON maintenance_history BEGIN
            UPDATE fts_kb SET 
                title = coalesce(new.title, new.type),
                content = new.comments
            WHERE record_type = 'maintenance' AND record_id = old.id;
        END;
        """)
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_maintenance_delete AFTER DELETE ON maintenance_history BEGIN
            DELETE FROM fts_kb WHERE record_type = 'maintenance' AND record_id = old.id;
        END;
        """)
        
        # Parts Triggers
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_parts_insert AFTER INSERT ON installed_parts BEGIN
            INSERT INTO fts_kb(record_type, record_id, title, content, tags)
            VALUES ('part', new.id, new.part_name, new.comments, '');
        END;
        """)
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_parts_update AFTER UPDATE ON installed_parts BEGIN
            UPDATE fts_kb SET 
                title = new.part_name,
                content = new.comments
            WHERE record_type = 'part' AND record_id = old.id;
        END;
        """)
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_parts_delete AFTER DELETE ON installed_parts BEGIN
            DELETE FROM fts_kb WHERE record_type = 'part' AND record_id = old.id;
        END;
        """)
        
        # Instructions Triggers
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_instructions_insert AFTER INSERT ON user_instructions BEGIN
            INSERT INTO fts_kb(record_type, record_id, title, content, tags)
            VALUES ('instruction', new.id, new.title, new.content, new.tags);
        END;
        """)
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_instructions_update AFTER UPDATE ON user_instructions BEGIN
            UPDATE fts_kb SET 
                title = new.title,
                content = new.content,
                tags = new.tags
            WHERE record_type = 'instruction' AND record_id = old.id;
        END;
        """)
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_instructions_delete AFTER DELETE ON user_instructions BEGIN
            DELETE FROM fts_kb WHERE record_type = 'instruction' AND record_id = old.id;
        END;
        """)
        
        conn.commit()
        conn.close()

    def list_databases(self):
        dbs = []
        for file in os.listdir(self.data_dir):
            if file.endswith(".db"):
                db_path = os.path.join(self.data_dir, file)
                size = os.path.getsize(db_path)
                mtime = os.path.getmtime(db_path)
                dbs.append({
                    "name": file[:-3],
                    "filename": file,
                    "size_bytes": size,
                    "last_modified": datetime.fromtimestamp(mtime).isoformat()
                })
        return dbs

    def create_database(self, name):
        name = os.path.basename(name).strip()
        if not name:
            raise Exception("Invalid database name")
        db_filename = name if name.endswith(".db") else name + ".db"
        db_path = self.get_db_path(db_filename)
        if os.path.exists(db_path):
            raise Exception("Database already exists")
        
        self.set_active_db(db_filename)
        return db_filename

    def delete_database(self, name):
        name = os.path.basename(name)
        db_filename = name if name.endswith(".db") else name + ".db"
        db_path = self.get_db_path(db_filename)
        if not os.path.exists(db_path):
            raise Exception("Database not found")
        
        if self.active_db_name == db_filename:
            self.active_db_name = None
            self.active_db_path = None
            self.save_last_active_db()
            
        os.remove(db_path)
        att_dir = os.path.join(self.data_dir, "attachments", db_filename[:-3])
        if os.path.exists(att_dir):
            shutil.rmtree(att_dir)

    def rename_database(self, old_name, new_name):
        old_name = os.path.basename(old_name).strip()
        new_name = os.path.basename(new_name).strip()
        if not old_name or not new_name:
            raise Exception("Invalid database name")
            
        old_filename = old_name if old_name.endswith(".db") else old_name + ".db"
        new_filename = new_name if new_name.endswith(".db") else new_name + ".db"
        
        old_path = self.get_db_path(old_filename)
        new_path = self.get_db_path(new_filename)
        
        if not os.path.exists(old_path):
            raise Exception("Source database not found")
        if os.path.exists(new_path):
            raise Exception("Target database already exists")
            
        os.rename(old_path, new_path)
        
        old_att_dir = os.path.join(self.data_dir, "attachments", old_filename[:-3])
        new_att_dir = os.path.join(self.data_dir, "attachments", new_filename[:-3])
        if os.path.exists(old_att_dir):
            os.rename(old_att_dir, new_att_dir)
            
        if self.active_db_name == old_filename:
            self.active_db_name = new_filename
            self.active_db_path = new_path
            self.save_last_active_db()
            
        return new_filename

    def search_kb(self, query):
        if not query.strip():
            return []
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        sql = """
            SELECT record_type, record_id, rank, title, snippet(fts_kb, 3, '<b>', '</b>', '...', 10) as snippet, tags
            FROM fts_kb 
            WHERE fts_kb MATCH ?
            ORDER BY rank
            LIMIT 50
        """
        clean_query = query.strip()
        terms = [t for t in clean_query.split() if t]
        match_query = " AND ".join([f"{t}*" for t in terms])
        
        results = []
        try:
            cursor.execute(sql, (match_query,))
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    "record_type": r["record_type"],
                    "record_id": r["record_id"],
                    "title": r["title"],
                    "snippet": r["snippet"],
                    "tags": r["tags"]
                })
        except sqlite3.OperationalError:
            fallback_sql = """
                SELECT record_type, record_id, title, tags
                FROM fts_kb
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                LIMIT 50
            """
            like_param = f"%{clean_query}%"
            cursor.execute(fallback_sql, (like_param, like_param, like_param))
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    "record_type": r["record_type"],
                    "record_id": r["record_id"],
                    "title": r["title"],
                    "snippet": r["title"],
                    "tags": r["tags"]
                })
        finally:
            conn.close()
        return results

    def create_backup(self):
        if not self.active_db_name:
            raise Exception("No active database to backup")
            
        db_base = self.active_db_name[:-3]
        timestamp = datetime.now().strftime("%Y-%m-%d")
        backup_filename = f"KM_Print_Fix_Hub_Backup_{db_base}_{timestamp}.zip"
        backup_path = os.path.join(self.backup_dir, backup_filename)
        
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(self.active_db_path, arcname=self.active_db_name)
            
            att_dir = os.path.join(self.data_dir, "attachments", db_base)
            if os.path.exists(att_dir):
                for root, _, files in os.walk(att_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, self.data_dir)
                        zipf.write(file_path, arcname=rel_path)
                        
        return backup_filename

    def restore_backup(self, zip_filepath):
        if not zipfile.is_zipfile(zip_filepath):
            raise Exception("Invalid backup file (not a ZIP archive)")
            
        with zipfile.ZipFile(zip_filepath, "r") as zipf:
            db_files = [f for f in zipf.namelist() if f.endswith(".db") and "/" not in f]
            if not db_files:
                raise Exception("No SQLite database found in backup ZIP")
                
            db_name = db_files[0]
            db_base = db_name[:-3]
            
            zipf.extract(db_name, path=self.data_dir)
            
            for item in zipf.namelist():
                if item.startswith(f"attachments/{db_base}/"):
                    zipf.extract(item, path=self.data_dir)
                    
            self.set_active_db(db_name)
            return db_name

    def export_to_json(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        tables = ["settings", "solutions", "maintenance_history", "installed_parts", "user_instructions", "related_records"]
        export_data = {}
        
        for table in tables:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            export_data[table] = [dict(r) for r in rows]
            
        conn.close()
        return export_data

    def import_from_json(self, export_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        tables = ["settings", "solutions", "maintenance_history", "installed_parts", "user_instructions", "related_records"]
        
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            
        for table in tables:
            rows = export_data.get(table, [])
            if not rows:
                continue
            cols = list(rows[0].keys())
            placeholders = ", ".join(["?"] * len(cols))
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
            
            records = []
            for r in rows:
                records.append([r[col] for col in cols])
                
            cursor.executemany(sql, records)
            
        cursor.execute("DELETE FROM fts_kb")
        
        cursor.execute("SELECT id, title, symptom, cause, solution, actions, result, tags FROM solutions")
        for r in cursor.fetchall():
            content = " ".join([coalesce(r[k]) for k in ["symptom", "cause", "solution", "actions", "result"]])
            cursor.execute("INSERT INTO fts_kb(record_type, record_id, title, content, tags) VALUES ('solution', ?, ?, ?, ?)",
                           (r["id"], r["title"], content, r["tags"]))
                           
        cursor.execute("SELECT id, type, title, comments FROM maintenance_history")
        for r in cursor.fetchall():
            title_val = r["title"] if r["title"] else r["type"]
            cursor.execute("INSERT INTO fts_kb(record_type, record_id, title, content, tags) VALUES ('maintenance', ?, ?, ?, '')",
                           (r["id"], title_val, r["comments"]))
                           
        cursor.execute("SELECT id, part_name, comments FROM installed_parts")
        for r in cursor.fetchall():
            cursor.execute("INSERT INTO fts_kb(record_type, record_id, title, content, tags) VALUES ('part', ?, ?, ?, '')",
                           (r["id"], r["part_name"], r["comments"]))
                           
        cursor.execute("SELECT id, title, content, tags FROM user_instructions")
        for r in cursor.fetchall():
            cursor.execute("INSERT INTO fts_kb(record_type, record_id, title, content, tags) VALUES ('instruction', ?, ?, ?, ?)",
                           (r["id"], r["title"], r["content"], r["tags"]))
        
        conn.commit()
        conn.close()

def coalesce(val):
    return val if val else ""
