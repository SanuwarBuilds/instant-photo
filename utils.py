import json
import os
import uuid
import bcrypt
import tempfile

try:
    import fcntl
except ImportError:
    fcntl = None

if os.environ.get("VERCEL"):
    CONFIG_FILE = os.path.join("/tmp", "config.json")
    DEFAULT_CONFIG_FILE = os.path.join("data", "config.json")
else:
    CONFIG_FILE = os.path.join("data", "config.json")
    DEFAULT_CONFIG_FILE = None

def lock_file(f, exclusive=True):
    if fcntl:
        try:
            fcntl.flock(f, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        except Exception:
            pass

def unlock_file(f):
    if fcntl:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        except Exception:
            pass

def load_config():
    if not os.path.exists(CONFIG_FILE):
        if DEFAULT_CONFIG_FILE and os.path.exists(DEFAULT_CONFIG_FILE):
            data = {}
            try:
                with open(DEFAULT_CONFIG_FILE, "r") as f:
                    lock_file(f, exclusive=False)
                    content = f.read()
                    unlock_file(f)
                data = json.loads(content) if content.strip() else {}
            except Exception as e:
                print(f"Error loading default config: {e}")
                data = {}
            
            save_config(data)
            return data
        return {}
    
    try:
        with open(CONFIG_FILE, "r") as f:
            lock_file(f, exclusive=False)
            content = f.read()
            unlock_file(f)
            return json.loads(content) if content.strip() else {}
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def save_config(config_data):
    dir_name = os.path.dirname(CONFIG_FILE)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    
    fd, temp_path = tempfile.mkstemp(dir=dir_name)
    try:
        with os.fdopen(fd, "w") as f:
            lock_file(f, exclusive=True)
            json.dump(config_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            unlock_file(f)
        os.replace(temp_path, CONFIG_FILE)
    except Exception as e:
        print(f"Error saving config: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def get_active_api_key(service="remove_bg"):
    config = load_config()
    keys = config.get("api_keys", [])
    for key in keys:
        if key.get("service") == service and key.get("active"):
            return key
    return None

def rotate_api_key(failed_key_id, service="remove_bg"):
    """Marks failed_key_id as inactive, activates the next available key for the service."""
    config = load_config()
    keys = config.get("api_keys", [])
    
    # 1. Mark current as failed
    for k in keys:
        if k.get("id") == failed_key_id:
            k["active"] = False
            k["last_failed"] = True

    # 2. Find next available key
    for k in keys:
        if k.get("service") == service and not k.get("last_failed"):
            k["active"] = True
            save_config(config)
            return k
            
    # If all failed, reset last_failed and try again? Or just fail. Let's just fail.
    save_config(config)
    return None
