from flask import Flask, request, render_template, send_file, session, redirect, jsonify, url_for
from PIL import Image, ImageOps
from io import BytesIO
from dotenv import load_dotenv
import requests
import uuid
import datetime
import utils
load_dotenv()
import cloudinary
import cloudinary.uploader
import cloudinary.utils
import os
import re
import zipfile
from werkzeug.exceptions import RequestEntityTooLarge

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "SANUWAR_PHOTO_SECRET")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "32")) * 1024 * 1024
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("FLASK_COOKIE_SECURE", "1" if os.getenv("VERCEL") else "0") == "1",
)

MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_MB", "8")) * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = int(os.getenv("MAX_TOTAL_IMAGE_MB", "24")) * 1024 * 1024
MAX_IMAGES_PER_REQUEST = int(os.getenv("MAX_IMAGES_PER_REQUEST", "8"))
MAX_COPIES_PER_IMAGE = int(os.getenv("MAX_COPIES_PER_IMAGE", "54"))
MAX_OUTPUT_PAGES = int(os.getenv("MAX_OUTPUT_PAGES", "6"))
REQUEST_TIMEOUT = (10, 75)
GITHUB_TIMEOUT = 10
ENHANCE_TIMEOUT = (10, 75)
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@app.errorhandler(RequestEntityTooLarge)
def handle_large_request(_error):
    return jsonify({
        "error": "upload_too_large",
        "message": f"Total upload limit is {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB."
    }), 413

def get_live_downloads_data():
    import json, os, requests, base64
    if os.environ.get("VERCEL"):
        github_pat = os.getenv("GITHUB_PAT")
        github_user = os.getenv("GITHUB_USER")
        github_repo = os.getenv("GITHUB_REPO")
        if github_pat and github_user and github_repo:
            try:
                url = f"https://api.github.com/repos/{github_user}/{github_repo}/contents/data/downloads.json"
                headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github.v3+json"}
                res = requests.get(url, headers=headers, timeout=GITHUB_TIMEOUT)
                if res.status_code == 200:
                    content = res.json().get("content", "")
                    decoded = base64.b64decode(content).decode("utf-8")
                    return json.loads(decoded)
            except Exception:
                pass
    try:
        with open("data/downloads.json", "r") as f:
            return json.load(f)
    except Exception:
        return []

REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)


@app.before_request
def check_maintenance():
    config = utils.load_config()
    maintenance = config.get("maintenance", {})
    if maintenance.get("enabled"):
        # Allow admin routes
        if request.path.startswith("/admin") or request.path.startswith("/api/admin") or request.path == "/api/maintenance/status":
            return
        
        # If API request
        if request.path.startswith("/api/") or request.path == "/process":
            return jsonify({"error": "maintenance", "message": maintenance.get("message")}), 503
        
        # If HTML request
        return render_template("maintenance.html", message=maintenance.get("message")), 503

@app.route("/api/maintenance/status")
def maintenance_status():
    config = utils.load_config()
    return jsonify({"enabled": config.get("maintenance", {}).get("enabled", False)})


# --- ADMIN ROUTES ---

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/admin")
@login_required
def admin_dashboard():
    return render_template("admin.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        username = data.get("username")
        password = data.get("password")
        
        config = utils.load_config()
        admin_conf = config.get("admin", {})
        
        if username == admin_conf.get("username") and utils.check_password(password, admin_conf.get("password_hash")):
            session["admin_logged_in"] = True
            return jsonify({"success": True})
        return jsonify({"error": "Invalid credentials"}), 401
    
    return render_template("login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

@app.route("/api/admin/dashboard")
@login_required
def api_admin_dashboard():
    try:
        config = utils.load_config()
        keys = config.get("api_keys", [])
        active_key = next((k for k in keys if k.get("active")), None)
        analytics = config.get("analytics", {})
        
        return jsonify({
            "total_keys": len(keys),
            "active_key_label": active_key.get("label") if active_key else "None",
            "maintenance_enabled": config.get("maintenance", {}).get("enabled", False),
            "analytics": {
                "total_generations": analytics.get("total_generations", 0),
                "total_failures": analytics.get("total_failures", 0),
                "total_images": analytics.get("total_images", 0),
                "formats": analytics.get("formats", {}),
                "presets": analytics.get("presets", {}),
                "errors": analytics.get("errors", {}),
                "last_event_at": analytics.get("last_event_at"),
                "daily_history": analytics.get("daily_history", {})
            }
        })
    except Exception as e:
        print(f"Error in api_admin_dashboard: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/admin/keys", methods=["GET", "POST"])
@login_required
def api_admin_keys():
    try:
        config = utils.load_config()
        if request.method == "GET":
            keys = config.get("api_keys", [])
            # Mask keys
            masked_keys = []
            for k in keys:
                km = k.copy()
                kn = km["key"]
                km["key"] = kn[:6] + "..." + kn[-4:] if len(kn) > 10 else "***"
                masked_keys.append(km)
            return jsonify(masked_keys)
            
        if request.method == "POST":
            data = request.json
            new_key = {
                "id": str(uuid.uuid4()),
                "service": data.get("service", "remove_bg"),
                "key": data.get("key"),
                "label": data.get("label", "New Key"),
                "active": data.get("active", False),
                "added_at": datetime.datetime.now().isoformat(),
                "usage_count": 0,
                "last_failed": None
            }
            config.setdefault("api_keys", []).append(new_key)
            utils.save_config(config)
            return jsonify({"success": True, "key": new_key})
    except Exception as e:
        print(f"Error in api_admin_keys: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/admin/keys/<key_id>/activate", methods=["POST"])
@login_required
def api_admin_activate_key(key_id):
    try:
        config = utils.load_config()
        keys = config.get("api_keys", [])
        
        # Find key to see its service
        target_key = next((k for k in keys if k.get("id") == key_id), None)
        if not target_key:
            return jsonify({"error": "key_not_found"}), 404
            
        service = target_key.get("service")
        
        # Deactivate others in same service, activate this one
        for k in keys:
            if k.get("service") == service:
                k["active"] = (k.get("id") == key_id)
                if k["active"]:
                    k["last_failed"] = None # Reset fail state on manual activation
                    
        utils.save_config(config)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error in api_admin_activate_key: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/admin/keys/<key_id>", methods=["DELETE"])
@login_required
def api_admin_delete_key(key_id):
    try:
        config = utils.load_config()
        keys = config.get("api_keys", [])
        config["api_keys"] = [k for k in keys if k.get("id") != key_id]
        utils.save_config(config)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error in api_admin_delete_key: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/admin/keys/<key_id>/check", methods=["POST"])
@login_required
def api_admin_check_key(key_id):
    try:
        config = utils.load_config()
        keys = config.get("api_keys", [])
        target_key = next((k for k in keys if k.get("id") == key_id), None)
        if not target_key:
            return jsonify({"error": "key_not_found"}), 404
        
        api_key = target_key.get("key")
        # Call remove.bg account endpoint
        res = requests.get(
            "https://api.remove.bg/v1.0/account",
            headers={"X-Api-Key": api_key},
            timeout=5
        )
        
        if res.status_code == 200:
            data = res.json().get("data", {})
            attributes = data.get("attributes", {})
            credits = attributes.get("credits", {})
            api = attributes.get("api", {})
            
            total_credits = credits.get("total", 0)
            free_calls = api.get("free_calls", 0)
            
            # Update key in config
            target_key["last_failed"] = None
            target_key["credits_info"] = {
                "total": total_credits,
                "free_calls": free_calls,
                "checked_at": datetime.datetime.now().isoformat()
            }
            utils.save_config(config)
            
            return jsonify({
                "success": True,
                "status": "healthy",
                "credits": total_credits,
                "free_calls": free_calls
            })
        else:
            error_msg = "Invalid key"
            try:
                errors = res.json().get("errors", [])
                if errors:
                    error_msg = errors[0].get("title", error_msg)
            except:
                pass
            
            target_key["last_failed"] = True
            utils.save_config(config)
            return jsonify({
                "success": False,
                "status": "failed",
                "error": error_msg,
                "http_code": res.status_code
            })
    except Exception as e:
        print(f"Error checking key health: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/maintenance", methods=["POST"])
@login_required
def api_admin_maintenance():
    try:
        data = request.json
        config = utils.load_config()
        maintenance = config.setdefault("maintenance", {})
        maintenance["enabled"] = bool(data.get("enabled"))
        if "message" in data:
            maintenance["message"] = data.get("message")
        utils.save_config(config)
        return jsonify({"success": True, "maintenance": maintenance})
    except Exception as e:
        print(f"Error in api_admin_maintenance: {e}")
        return jsonify({"error": "Internal server error"}), 500


# --- COUNTDOWN ROUTES ---

@app.route("/api/countdowns", methods=["GET"])
def api_get_countdowns_public():
    """Public endpoint — returns only enabled countdowns for the home page."""
    config = utils.load_config()
    all_cds = config.get("countdowns", [])
    enabled = [c for c in all_cds if c.get("enabled")]
    return jsonify(enabled)

@app.route("/api/admin/countdowns", methods=["GET"])
@login_required
def api_admin_get_countdowns():
    config = utils.load_config()
    return jsonify(config.get("countdowns", []))

@app.route("/api/admin/countdowns", methods=["POST"])
@login_required
def api_admin_add_countdown():
    try:
        data = request.json
        if not data.get("title") or not data.get("target_date"):
            return jsonify({"error": "title and target_date are required"}), 400
        config = utils.load_config()
        new_cd = {
            "id": str(uuid.uuid4()),
            "title": data["title"],
            "target_date": data["target_date"],
            "enabled": bool(data.get("enabled", True)),
            "created_at": datetime.datetime.now().isoformat()
        }
        config.setdefault("countdowns", []).append(new_cd)
        utils.save_config(config)
        return jsonify({"success": True, "countdown": new_cd})
    except Exception as e:
        print(f"Error adding countdown: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/admin/countdowns/<cd_id>", methods=["PUT"])
@login_required
def api_admin_update_countdown(cd_id):
    try:
        data = request.json
        config = utils.load_config()
        countdowns = config.get("countdowns", [])
        cd = next((c for c in countdowns if c["id"] == cd_id), None)
        if not cd:
            return jsonify({"error": "not_found"}), 404
        if "title" in data:
            cd["title"] = data["title"]
        if "target_date" in data:
            cd["target_date"] = data["target_date"]
        if "enabled" in data:
            cd["enabled"] = bool(data["enabled"])
        utils.save_config(config)
        return jsonify({"success": True, "countdown": cd})
    except Exception as e:
        print(f"Error updating countdown: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/admin/countdowns/<cd_id>", methods=["DELETE"])
@login_required
def api_admin_delete_countdown(cd_id):
    try:
        config = utils.load_config()
        config["countdowns"] = [c for c in config.get("countdowns", []) if c["id"] != cd_id]
        utils.save_config(config)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting countdown: {e}")
        return jsonify({"error": "Internal server error"}), 500


# --- WIDGET ROUTES (Home Screen Builder) ---

@app.route("/api/widgets", methods=["GET"])
def api_widgets_public():
    """Public — returns all enabled widgets sorted by order."""
    config = utils.load_config()
    widgets = [w for w in config.get("widgets", []) if w.get("enabled")]
    widgets.sort(key=lambda x: x.get("order", 0))
    return jsonify(widgets)

@app.route("/api/admin/widgets", methods=["GET"])
@login_required
def api_admin_widgets_get():
    config = utils.load_config()
    widgets = config.get("widgets", [])
    widgets.sort(key=lambda x: x.get("order", 0))
    return jsonify(widgets)

@app.route("/api/admin/widgets", methods=["POST"])
@login_required
def api_admin_widgets_add():
    try:
        data = request.json
        if not data.get("type"):
            return jsonify({"error": "type is required"}), 400
        config = utils.load_config()
        widgets = config.get("widgets", [])
        new_widget = {
            "id": str(uuid.uuid4()),
            "type": data["type"],
            "enabled": bool(data.get("enabled", True)),
            "order": len(widgets),
            "data": data.get("data", {}),
            "created_at": datetime.datetime.now().isoformat()
        }
        widgets.append(new_widget)
        config["widgets"] = widgets
        utils.save_config(config)
        return jsonify({"success": True, "widget": new_widget})
    except Exception as e:
        print(f"Error adding widget: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/admin/upload", methods=["POST"])
@login_required
def api_admin_upload():
    try:
        import cloudinary.uploader
        
        # Check if JSON payload (Base64)
        if request.is_json:
            data = request.json
            if "file" not in data:
                return jsonify({"error": "No file provided in JSON"}), 400
            file_data = data["file"]
            import re
            filename = data.get("filename", "file")
            pid = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
            upload_result = cloudinary.uploader.upload(file_data, resource_type="raw", public_id=pid)
        else:
            # Fallback to Multipart
            if "image" not in request.files:
                return jsonify({"error": "No image file provided"}), 400
            file = request.files["image"]
            if file.filename == "":
                return jsonify({"error": "No selected file"}), 400
            import re
            pid = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', file.filename)
            upload_result = cloudinary.uploader.upload(file, resource_type="raw", public_id=pid)
            
        secure_url = upload_result.get("secure_url")
        return jsonify({"success": True, "url": secure_url})
    except Exception as e:
        print(f"Widget Image Upload Error: {e}")
        return jsonify({"error": "Cloudinary upload failed: " + str(e)}), 500

@app.route("/api/admin/cloudinary-signature", methods=["POST"])
@login_required
def api_admin_cloudinary_signature():
    try:
        import time
        import cloudinary.utils
        import re
        
        data = request.json
        if not data or "public_id" not in data:
            return jsonify({"error": "Missing public_id"}), 400
            
        filename = data["public_id"]
        # Same strict validation logic as before
        pid = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        
        timestamp = int(time.time())
        params_to_sign = {
            'timestamp': timestamp,
            'public_id': pid
        }
        
        signature = cloudinary.utils.api_sign_request(
            params_to_sign, 
            os.getenv("CLOUDINARY_API_SECRET")
        )
        
        return jsonify({
            "signature": signature,
            "timestamp": timestamp,
            "public_id": pid,
            "api_key": os.getenv("CLOUDINARY_API_KEY"),
            "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME")
        })
    except Exception as e:
        print(f"Signature Generation Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/widgets/<widget_id>", methods=["PUT"])
@login_required
def api_admin_widgets_update(widget_id):
    try:
        data = request.json
        config = utils.load_config()
        widgets = config.get("widgets", [])
        w = next((x for x in widgets if x["id"] == widget_id), None)
        if not w:
            return jsonify({"error": "not_found"}), 404
        if "enabled" in data: w["enabled"] = bool(data["enabled"])
        if "order" in data:   w["order"]   = int(data["order"])
        if "data" in data:    w["data"]    = data["data"]
        config["widgets"] = widgets
        utils.save_config(config)
        return jsonify({"success": True, "widget": w})
    except Exception as e:
        print(f"Error updating widget: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/admin/widgets/<widget_id>", methods=["DELETE"])
@login_required
def api_admin_widgets_delete(widget_id):
    try:
        config = utils.load_config()
        config["widgets"] = [w for w in config.get("widgets", []) if w["id"] != widget_id]
        utils.save_config(config)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting widget: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/admin/widgets/reorder", methods=["POST"])
@login_required
def api_admin_widgets_reorder():
    try:
        order = request.json.get("order", [])
        config = utils.load_config()
        widgets = config.get("widgets", [])
        id_to_pos = {wid: idx for idx, wid in enumerate(order)}
        for w in widgets:
            if w["id"] in id_to_pos:
                w["order"] = id_to_pos[w["id"]]
        config["widgets"] = widgets
        utils.save_config(config)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def sync_store_apps_to_github(items=None):
    try:
        import os, shutil, requests, base64, json
        # Always sync to local frontend first
        if items is not None:
            content = json.dumps(items, indent=2)
            if not os.environ.get("VERCEL"):
                with open("github-pages-app/data.json", "w") as f:
                    f.write(content)
        else:
            if not os.environ.get("VERCEL"):
                shutil.copy("data/downloads.json", "github-pages-app/data.json")
            with open("data/downloads.json", "r") as f:
                content = f.read()
        
        # Github Sync
        github_pat = os.getenv("GITHUB_PAT")
        github_user = os.getenv("GITHUB_USER")
        github_repo = os.getenv("GITHUB_REPO")
        
        if not github_pat or not github_user or not github_repo:
            print("Github Sync skipped: Missing GITHUB_PAT, GITHUB_USER or GITHUB_REPO in .env")
            return
            
        url = f"https://api.github.com/repos/{github_user}/{github_repo}/contents/data/downloads.json"
        headers = {
            "Authorization": f"token {github_pat}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Get SHA
        get_res = requests.get(url, headers=headers)
        sha = get_res.json().get("sha") if get_res.status_code == 200 else None
        
        payload = {
            "message": "Auto-sync store apps from Admin Panel",
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")
        }
        if sha:
            payload["sha"] = sha
            
        put_res = requests.put(url, headers=headers, json=payload)
        if put_res.status_code in [200, 201]:
            print("Successfully synced to GitHub!")
        else:
            print(f"Failed to sync to GitHub: {put_res.text}")
    except Exception as e:
            print(f"Error syncing to github: {e}")

@app.route("/api/admin/store-apps/sync", methods=["POST"])
@login_required
def api_admin_sync():
    sync_store_apps_to_github()
    return jsonify({"success": True})

@app.route("/api/admin/store-apps", methods=["GET", "POST"])
@login_required
def create_store_app():
    import json
    # GET — return all items
    if request.method == "GET":
        items = get_live_downloads_data()
        return jsonify(items)
    try:
        data = request.json
        items = get_live_downloads_data()
            
        new_app = {
            "id": f"app_{uuid.uuid4().hex[:8]}",
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "link": data.get("link", ""),
            "image": data.get("image", ""),
            "category": data.get("category", "Apps"),
            "version": data.get("version", ""),
            "is_album": data.get("is_album", False),
            "album_files": data.get("album_files", [])
        }
        
        items.insert(0, new_app) # Add to top
        import os
        if not os.environ.get("VERCEL"):
            with open("data/downloads.json", "w") as f:
                json.dump(items, f, indent=2)
            
        sync_store_apps_to_github(items)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/store-apps/<app_id>", methods=["PUT"])
@login_required
def update_store_app(app_id):
    import json
    try:
        data = request.json
        items = get_live_downloads_data()
            
        for idx, item in enumerate(items):
            if item.get("id") == app_id:
                items[idx]["title"] = data.get("title", item["title"])
                items[idx]["description"] = data.get("description", item["description"])
                items[idx]["link"] = data.get("link", item["link"])
                items[idx]["image"] = data.get("image", item["image"])
                items[idx]["category"] = data.get("category", item["category"])
                items[idx]["version"] = data.get("version", item.get("version", ""))
                if "is_album" in data:
                    items[idx]["is_album"] = data["is_album"]
                if "album_files" in data:
                    items[idx]["album_files"] = data["album_files"]
                break
                
        import os
        if not os.environ.get("VERCEL"):
            with open("data/downloads.json", "w") as f:
                json.dump(items, f, indent=2)
            
        sync_store_apps_to_github(items)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/store-apps/<app_id>", methods=["DELETE"])
@login_required
def delete_store_app(app_id):
    import json
    try:
        items = get_live_downloads_data()
        
        # Find the item to delete
        item_to_delete = next((x for x in items if x.get("id") == app_id), None)
        if not item_to_delete:
            return jsonify({"error": "Item not found"}), 404

        # Optionally destroy from Cloudinary
        try:
            import cloudinary.uploader
            links_to_delete = []
            if item_to_delete.get("is_album"):
                for af in item_to_delete.get("album_files", []):
                    links_to_delete.append(af.get("link", ""))
            else:
                links_to_delete.append(item_to_delete.get("link", ""))
                
            for link in links_to_delete:
                if link and "res.cloudinary.com" in link:
                    # Extract public_id from URL
                    parts = link.split("/upload/")
                    if len(parts) > 1:
                        public_id = parts[1].rsplit(".", 1)[0]
                        # Strip any transformations
                        public_id = public_id.replace("fl_attachment/", "")
                        try:
                            cloudinary.uploader.destroy(public_id, resource_type="image")
                        except:
                            pass
                        try:
                            cloudinary.uploader.destroy(public_id, resource_type="raw")
                        except:
                            pass
        except Exception as cloud_err:
            print(f"Cloudinary delete warning (non-fatal): {cloud_err}")

        # Remove from list
        items = [x for x in items if x.get("id") != app_id]
        
        import os
        if not os.environ.get("VERCEL"):
            with open("data/downloads.json", "w") as f:
                json.dump(items, f, indent=2)
            
        sync_store_apps_to_github(items)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/widgets/<widget_id>/vote", methods=["POST"])
def api_widget_vote(widget_id):

    """Session-protected poll voting."""
    try:
        data = request.json
        option_id = data.get("option_id")
        if not option_id:
            return jsonify({"error": "option_id required"}), 400
        voted_key = f"voted_{widget_id}"
        if session.get(voted_key):
            return jsonify({"error": "already_voted"}), 403
        config = utils.load_config()
        widgets = config.get("widgets", [])
        w = next((x for x in widgets if x["id"] == widget_id and x["type"] == "poll"), None)
        if not w:
            return jsonify({"error": "poll_not_found"}), 404
        options = w["data"].get("options", [])
        opt = next((o for o in options if o["id"] == option_id), None)
        if not opt:
            return jsonify({"error": "option_not_found"}), 404
        opt["votes"] = opt.get("votes", 0) + 1
        config["widgets"] = widgets
        utils.save_config(config)
        session[voted_key] = True
        return jsonify({"success": True, "options": options})
    except Exception as e:
        print(f"Error voting: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/downloads")
def downloads():
    return render_template("downloads.html")

@app.route("/api/downloads_data")
def api_downloads_data():
    data = get_live_downloads_data()
    return jsonify(data)


@app.route("/sitemap.xml")
def sitemap():
    import datetime
    from flask import Response
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{request.host_url.rstrip('/')}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return Response(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    from flask import Response
    txt = f"User-agent: *\nAllow: /\nSitemap: {request.host_url.rstrip('/')}/sitemap.xml\n"
    return Response(txt, mimetype="text/plain")


@app.route("/manifest.webmanifest")
def manifest():
    return jsonify({
        "name": "Sanuwar Instant Photo",
        "short_name": "Instant Photo",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#111827",
        "theme_color": "#2563eb",
        "description": "Create print-ready passport photo sheets.",
        "icons": [
            {
                "src": "https://res.cloudinary.com/dcajb02df/image/upload/v1753960691/logo_pyncju.png",
                "sizes": "192x192",
                "type": "image/png"
            }
        ]
    })


@app.route("/service-worker.js")
def service_worker():
    from flask import Response
    js = """
const CACHE_NAME = 'instant-photo-shell-v1';
const SHELL = ['/', '/downloads', '/manifest.webmanifest'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))));
  self.clients.claim();
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
"""
    return Response(js, mimetype="application/javascript")


def has_remove_bg_key():
    return bool(utils.get_active_api_key("remove_bg") or REMOVE_BG_API_KEY)


def parse_int_field(name, default, min_value, max_value):
    try:
        value = int(request.form.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(min_value, min(max_value, value))


def parse_int_value(value, default, min_value, max_value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    return max(min_value, min(max_value, value))

def fix_image_rotation(image_bytes):
    try:
        img = Image.open(BytesIO(image_bytes))
        transposed_img = ImageOps.exif_transpose(img)
        out = BytesIO()
        fmt = img.format or "JPEG"
        transposed_img.save(out, format=fmt)
        return out.getvalue()
    except Exception as e:
        print(f"EXIF rotation correction failed: {e}")
        return image_bytes


def draw_dashed_line(draw, p1, p2, color=(200, 200, 200), width=1, dash_length=8, gap_length=6):
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    dist = (dx**2 + dy**2)**0.5
    if dist == 0:
        return
    dx /= dist
    dy /= dist
    
    current_dist = 0
    while current_dist < dist:
        seg_end = min(current_dist + dash_length, dist)
        draw.line([
            (x1 + dx * current_dist, y1 + dy * current_dist),
            (x1 + dx * seg_end, y1 + dy * seg_end)
        ], fill=color, width=width)
        current_dist += dash_length + gap_length


def clean_bg_color(value):
    value = (value or "#FFFFFF").strip()
    return value.upper() if HEX_COLOR_RE.match(value) else "#FFFFFF"


def validate_image_bytes(raw_bytes, filename="image"):
    if not raw_bytes:
        raise ValueError("empty_image")
    if len(raw_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("image_too_large")

    try:
        with Image.open(BytesIO(raw_bytes)) as img:
            img.verify()
        with Image.open(BytesIO(raw_bytes)) as img:
            width, height = img.size
            fmt = (img.format or "").upper()
    except Exception:
        raise ValueError("invalid_image")

    if fmt not in {"JPEG", "PNG", "WEBP"}:
        raise ValueError("unsupported_image_type")
    if width < 120 or height < 120:
        raise ValueError("image_too_small")
    if width * height > 30_000_000:
        raise ValueError("image_resolution_too_large")

    return {
        "filename": filename,
        "size": len(raw_bytes),
        "width": width,
        "height": height,
        "format": fmt,
    }


def record_generation(success, image_count=0, output_format="pdf", preset="custom", error=None):
    try:
        config = utils.load_config()
        analytics = config.setdefault("analytics", {})
        analytics["total_generations"] = analytics.get("total_generations", 0) + (1 if success else 0)
        analytics["total_failures"] = analytics.get("total_failures", 0) + (0 if success else 1)
        analytics["total_images"] = analytics.get("total_images", 0) + int(image_count or 0)
        analytics["last_event_at"] = datetime.datetime.now().isoformat()

        formats = analytics.setdefault("formats", {})
        formats[output_format] = formats.get(output_format, 0) + 1

        presets = analytics.setdefault("presets", {})
        presets[preset or "custom"] = presets.get(preset or "custom", 0) + 1

        if error:
            errors = analytics.setdefault("errors", {})
            errors[error] = errors.get(error, 0) + 1

        # Record daily history
        today_str = datetime.date.today().isoformat()
        history = analytics.setdefault("daily_history", {})
        day_stats = history.setdefault(today_str, {"success": 0, "failure": 0})
        if success:
            day_stats["success"] = day_stats.get("success", 0) + 1
        else:
            day_stats["failure"] = day_stats.get("failure", 0) + 1
            
        # Prune older than 60 days
        if len(history) > 60:
            sorted_days = sorted(history.keys())
            while len(history) > 60:
                oldest = sorted_days.pop(0)
                history.pop(oldest, None)

        utils.save_config(config)
    except Exception as e:
        print(f"Analytics save warning: {e}")


def hex_to_rgb(hex_color):
    """Convert a hex color string (e.g. '#3B82F6') to an (R, G, B) tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (255, 255, 255)  # Fallback to white
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def process_single_image(input_image_bytes, bg_color="#FFFFFF"):
    """Remove background, enhance, and return a ready-to-paste passport PIL image.

    Args:
        input_image_bytes: Raw image bytes for the upload.
        bg_color: Hex color string for the background (default white).
    """
    bg_rgb = hex_to_rgb(bg_color)

    # Step 1: Background removal via remove.bg (called ONCE per image)
    
    # Try with active key, if it fails due to quota, rotate and try next.
    max_retries = 2
    response = None
    
    for attempt in range(max_retries):
        active_key_info = utils.get_active_api_key("remove_bg")
        # If no active key defined in config, fallback to env variable
        current_api_key = active_key_info.get("key") if active_key_info else REMOVE_BG_API_KEY
        
        if not current_api_key:
            raise ValueError("No remove.bg API key available. Please add one in the Admin Panel.")

        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": input_image_bytes},
            data={"size": "auto"},
            headers={"X-Api-Key": current_api_key},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            # Success, increment usage count
            if active_key_info:
                config = utils.load_config()
                for k in config.get("api_keys", []):
                    if k.get("id") == active_key_info.get("id"):
                        k["usage_count"] = k.get("usage_count", 0) + 1
                        utils.save_config(config)
                        break
            break # Exit retry loop
            
        else:
            # Handle failure
            try:
                error_info = response.json()
                error_code = error_info.get("errors", [{}])[0].get("code", "unknown_error")
                error_title = error_info.get("errors", [{}])[0].get("title", "")
            except Exception:
                error_code = "unknown_error"
                error_title = response.text
                
            # If rate limited, out of credits, or unauthorized, try to rotate
            if response.status_code in [402, 403, 429] or "insufficient_credits" in error_code.lower() or "quota" in error_title.lower():
                if active_key_info and attempt < max_retries - 1:
                    print(f"API Key {active_key_info.get('label')} failed (Code: {response.status_code}). Rotating...")
                    next_key = utils.rotate_api_key(active_key_info.get("id"), "remove_bg")
                    if next_key:
                        continue # Retry with next key
                
            raise ValueError(f"bg_removal_failed:{error_code}:{response.status_code}")

    if not response or response.status_code != 200:
         raise ValueError(f"bg_removal_failed:unknown_error")

    bg_removed = BytesIO(response.content)
    img = Image.open(bg_removed)

    # Ensure RGBA so we can extract the alpha mask
    if img.mode not in ("RGBA", "LA"):
        img = img.convert("RGBA")

    # Step 2: Save the alpha mask BEFORE Cloudinary (gen_restore strips transparency)
    alpha_mask = img.split()[-1]

    # Flatten to white for Cloudinary enhancement (gives best quality results)
    flat_img = Image.new("RGB", img.size, (255, 255, 255))
    flat_img.paste(img, mask=alpha_mask)

    # Step 3: Upload flattened image to Cloudinary for AI enhancement
    buffer = BytesIO()
    flat_img.save(buffer, format="PNG")
    buffer.seek(0)
    upload_result = cloudinary.uploader.upload(buffer, resource_type="image")
    image_url = upload_result.get("secure_url")
    public_id = upload_result.get("public_id")

    if not image_url:
        raise ValueError("cloudinary_upload_failed")

    # Step 4: Enhance via Cloudinary AI
    enhanced_url = cloudinary.utils.cloudinary_url(
        public_id,
        transformation=[
            {"effect": "gen_restore"},
            {"quality": "100"},
            {"fetch_format": "png"},
        ],
    )[0]

    enhanced_res = requests.get(enhanced_url, timeout=ENHANCE_TIMEOUT)
    enhanced_res.raise_for_status()
    enhanced_img_data = enhanced_res.content
    enhanced_img = Image.open(BytesIO(enhanced_img_data)).convert("RGB")

    # Step 5: Resize alpha mask to match enhanced image (in case of size mismatch)
    if alpha_mask.size != enhanced_img.size:
        alpha_mask = alpha_mask.resize(enhanced_img.size, Image.LANCZOS)

    # Step 6: Composite the enhanced subject onto the user-selected background color
    background = Image.new("RGB", enhanced_img.size, bg_rgb)
    background.paste(enhanced_img, mask=alpha_mask)
    passport_img = background

    return passport_img


@app.route("/process", methods=["POST"])
def process():
    print("==== /process endpoint hit ====")

    output_format = (request.form.get("output_format") or "pdf").lower()
    if output_format not in {"pdf", "png", "jpg", "jpeg", "zip"}:
        output_format = "pdf"
    preset_name = (request.form.get("preset") or "custom").strip()[:40] or "custom"

    def fail(error, status=400, message=None, image_count=0):
        record_generation(False, image_count=image_count, output_format=output_format, preset=preset_name, error=error)
        payload = {"error": error}
        if message:
            payload["message"] = message
        return jsonify(payload), status

    if not has_remove_bg_key():
        return fail("missing_remove_bg_key", 500, "Add an active remove.bg key in Admin Panel or set REMOVE_BG_API_KEY.")
    if not CLOUDINARY_CLOUD_NAME or not os.getenv("CLOUDINARY_API_KEY") or not os.getenv("CLOUDINARY_API_SECRET"):
        return fail("missing_cloudinary_config", 500, "Cloudinary cloud name, API key, and API secret are required.")

    try:
        # Layout settings
        # Higher DPI scaling for maximum quality (600 DPI instead of 300 DPI)
        scale = 2
        passport_width = parse_int_field("width", 390, 120, 2000) * scale
        passport_height = parse_int_field("height", 480, 120, 3000) * scale
        border = parse_int_field("border", 2, 0, 20) * scale
        spacing = parse_int_field("spacing", 10, 0, 80) * scale
        cut_marks = request.form.get("cut_marks", "true") == "true"
        bg_color = clean_bg_color(request.form.get("bg_color", "#FFFFFF"))
        margin_x = 10 * scale
        margin_y = 10 * scale
        horizontal_gap = 10 * scale
        a4_w, a4_h = 2480 * scale, 3508 * scale

        # Collect images and their copy counts
        images_data = []
        total_upload_bytes = 0

        # Multi-image mode
        if f"image_{MAX_IMAGES_PER_REQUEST}" in request.files:
            return fail("too_many_images", 413, f"Maximum {MAX_IMAGES_PER_REQUEST} images are allowed per request.")

        for i in range(MAX_IMAGES_PER_REQUEST):
            if f"image_{i}" not in request.files:
                continue
            file = request.files[f"image_{i}"]
            raw = fix_image_rotation(file.read())
            meta = validate_image_bytes(raw, file.filename or f"image_{i}")
            total_upload_bytes += meta["size"]
            if total_upload_bytes > MAX_TOTAL_IMAGE_BYTES:
                return fail("total_upload_too_large", 413, f"Total image upload limit is {MAX_TOTAL_IMAGE_BYTES // (1024 * 1024)} MB.")
            copies = parse_int_value(request.form.get(f"copies_{i}", 6), 6, 1, MAX_COPIES_PER_IMAGE)
            images_data.append((raw, copies, meta))

        # Fallback to single image mode
        if not images_data and "image" in request.files:
            file = request.files["image"]
            raw = fix_image_rotation(file.read())
            meta = validate_image_bytes(raw, file.filename or "image")
            copies = parse_int_value(request.form.get("copies", 6), 6, 1, MAX_COPIES_PER_IMAGE)
            images_data.append((raw, copies, meta))

        if not images_data:
            return fail("no_image_uploaded", 400, "Please upload at least one image.")

        print(f"DEBUG: Processing {len(images_data)} image(s)")

        # Process all images
        passport_images = []
        for idx, (img_bytes, copies, meta) in enumerate(images_data):
            print(f"DEBUG: Processing image {idx + 1} with {copies} copies")
            try:
                img = process_single_image(img_bytes, bg_color=bg_color)
                img = img.resize((passport_width, passport_height), Image.LANCZOS)
                img = ImageOps.expand(img, border=border, fill="black")
                passport_images.append((img, copies))
            except ValueError as e:
                err_str = str(e)
                if "410" in err_str or "face" in err_str.lower() or "unknown_foreground" in err_str.lower():
                    return fail("face_detection_failed", 410, "Use a front-facing photo with plain background and good light.", len(images_data))
                elif "429" in err_str or "quota" in err_str.lower() or "402" in err_str or "insufficient_credits" in err_str.lower():
                    return fail("quota_exceeded", 429, "Daily remove.bg quota is exhausted. Try another API key in Admin Panel.", len(images_data))
                elif "403" in err_str or "auth_failed" in err_str.lower():
                    return fail("invalid_api_key", 500, "The active remove.bg API key is invalid or unauthorized.", len(images_data))
                else:
                    print(f"ERROR processing image {idx}: {err_str}")
                    return fail("processing_failed", 500, err_str, len(images_data))
            except requests.exceptions.Timeout:
                return fail("external_service_timeout", 504, "Image service timed out. Try a smaller image or try again.", len(images_data))
            except requests.exceptions.RequestException as e:
                print(f"External service error: {e}")
                return fail("external_service_error", 502, "Image service failed. Please try again.", len(images_data))
            except Exception as e:
                print(f"Unexpected image processing error: {e}")
                return fail("processing_failed", 500, "Image processing failed. Try again with a clearer photo.", len(images_data))

    except ValueError as e:
        err = str(e)
        status = 413 if "large" in err else 400
        messages = {
            "empty_image": "One uploaded image is empty.",
            "image_too_large": f"Each image must be under {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
            "invalid_image": "Please upload a valid JPG, PNG, or WEBP image.",
            "unsupported_image_type": "Only JPG, PNG, and WEBP images are supported.",
            "image_too_small": "Image is too small. Upload at least 120 x 120 px.",
            "image_resolution_too_large": "Image resolution is too large. Try a smaller image.",
        }
        return fail(err, status, messages.get(err, "Invalid upload."))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return fail("server_error", 500, str(e))

    try:
        paste_w = passport_width + 2 * border
        paste_h = passport_height + 2 * border

        # Calculate how many photos fit in one row + center offset
        cols_per_row = max(1, (a4_w + horizontal_gap) // (paste_w + horizontal_gap))
        total_row_width = cols_per_row * paste_w + (cols_per_row - 1) * horizontal_gap
        center_offset_x = (a4_w - total_row_width) // 2  # Equal left/right margins

        # Build all pages
        pages = []
        current_page = Image.new("RGB", (a4_w, a4_h), "white")
        x, y = center_offset_x, margin_y

        def new_page():
            nonlocal current_page, x, y
            if len(pages) + 1 >= MAX_OUTPUT_PAGES:
                raise ValueError("too_many_output_pages")
            pages.append(current_page)
            current_page = Image.new("RGB", (a4_w, a4_h), "white")
            x, y = center_offset_x, margin_y

        for passport_img, copies in passport_images:
            for _ in range(copies):
                # Move to next row if needed
                if x + paste_w > a4_w - center_offset_x:
                    x = center_offset_x
                    y += paste_h + spacing

                # Move to next page if needed
                if y + paste_h > a4_h - margin_y:
                    new_page()

                current_page.paste(passport_img, (x, y))
                
                if cut_marks:
                    from PIL import ImageDraw
                    draw = ImageDraw.Draw(current_page)
                    w = max(1, 1 * scale)
                    dl = 8 * scale
                    gl = 6 * scale
                    draw_dashed_line(draw, (x, y), (x + paste_w, y), color=(200, 200, 200), width=w, dash_length=dl, gap_length=gl)
                    draw_dashed_line(draw, (x, y + paste_h), (x + paste_w, y + paste_h), color=(200, 200, 200), width=w, dash_length=dl, gap_length=gl)
                    draw_dashed_line(draw, (x, y), (x, y + paste_h), color=(200, 200, 200), width=w, dash_length=dl, gap_length=gl)
                    draw_dashed_line(draw, (x + paste_w, y), (x + paste_w, y + paste_h), color=(200, 200, 200), width=w, dash_length=dl, gap_length=gl)
                    
                print(f"DEBUG: Placed at x={x}, y={y}")
                x += paste_w + horizontal_gap

        pages.append(current_page)
        print(f"DEBUG: Total pages = {len(pages)}")

        dpi_val = 300 * scale

        def build_pdf():
            pdf_output = BytesIO()
            if len(pages) == 1:
                pages[0].save(pdf_output, format="PDF", dpi=(dpi_val, dpi_val))
            else:
                pages[0].save(
                    pdf_output,
                    format="PDF",
                    dpi=(dpi_val, dpi_val),
                    save_all=True,
                    append_images=pages[1:],
                )
            pdf_output.seek(0)
            return pdf_output

        def attach_sheet_headers(response):
            response.headers["X-Page-Count"] = str(len(pages))
            response.headers["X-Print-Size"] = "A4 210mm x 297mm"
            response.headers["X-Output-Format"] = output_format
            return response

        record_generation(True, image_count=len(images_data), output_format=output_format, preset=preset_name)

        if output_format == "png":
            output = BytesIO()
            pages[0].save(output, format="PNG", dpi=(dpi_val, dpi_val))
            output.seek(0)
            response = send_file(
                output,
                mimetype="image/png",
                as_attachment=True,
                download_name="passport-sheet-page-1.png",
            )
            return attach_sheet_headers(response)

        if output_format in {"jpg", "jpeg"}:
            output = BytesIO()
            pages[0].save(output, format="JPEG", dpi=(dpi_val, dpi_val), quality=95)
            output.seek(0)
            response = send_file(
                output,
                mimetype="image/jpeg",
                as_attachment=True,
                download_name="passport-sheet-page-1.jpg",
            )
            return attach_sheet_headers(response)

        if output_format == "zip":
            zip_output = BytesIO()
            with zipfile.ZipFile(zip_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("passport-sheet.pdf", build_pdf().getvalue())
                for idx, page in enumerate(pages, start=1):
                    # Save PNG version
                    png_output = BytesIO()
                    page.save(png_output, format="PNG", dpi=(dpi_val, dpi_val))
                    archive.writestr(f"passport-sheet-page-{idx}.png", png_output.getvalue())
                    
                    # Save JPEG version (highly compatible for printing/Photoshop)
                    jpg_output = BytesIO()
                    page.save(jpg_output, format="JPEG", dpi=(dpi_val, dpi_val), quality=95)
                    archive.writestr(f"passport-sheet-page-{idx}.jpg", jpg_output.getvalue())
            zip_output.seek(0)
            response = send_file(
                zip_output,
                mimetype="application/zip",
                as_attachment=True,
                download_name="passport-sheet.zip",
            )
            return attach_sheet_headers(response)

        # Export multi-page PDF
        print("DEBUG: Returning PDF to client")
        response = send_file(
            build_pdf(),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="passport-sheet.pdf",
        )
        return attach_sheet_headers(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        if str(e) == "too_many_output_pages":
            return fail("too_many_output_pages", 413, f"Sheet would exceed {MAX_OUTPUT_PAGES} pages. Reduce copies or image count.")
        return fail("pdf_generation_failed", 500, str(e))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
