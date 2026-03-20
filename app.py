from flask import Flask, request, render_template, send_file
from PIL import Image, ImageOps
from io import BytesIO
from dotenv import load_dotenv
import requests

load_dotenv()
import cloudinary
import cloudinary.uploader
import cloudinary.utils
import os

app = Flask(__name__)

REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)


@app.route("/")
def index():
    return render_template("index.html")


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
    response = requests.post(
        "https://api.remove.bg/v1.0/removebg",
        files={"image_file": input_image_bytes},
        data={"size": "auto"},
        headers={"X-Api-Key": REMOVE_BG_API_KEY},
    )

    if response.status_code != 200:
        try:
            error_info = response.json()
            if error_info.get("errors"):
                error_code = error_info["errors"][0].get("code", "unknown_error")
                raise ValueError(f"bg_removal_failed:{error_code}:{response.status_code}")
        except ValueError:
            raise

        except Exception:
            pass
        raise ValueError(f"bg_removal_failed:unknown:{response.status_code}")

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
            {"quality": "auto"},
            {"fetch_format": "auto"},
        ],
    )[0]

    enhanced_img_data = requests.get(enhanced_url).content
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

    if not REMOVE_BG_API_KEY:
        return {"error": "Remove.bg API Key missing. Please provide .env or setup keys."}, 500
    if not CLOUDINARY_CLOUD_NAME:
        return {"error": "Cloudinary details missing. Please provide .env or setup keys."}, 500

    try:
        # Layout settings
        passport_width = int(request.form.get("width", 390))
        passport_height = int(request.form.get("height", 480))
        border = int(request.form.get("border", 2))
        spacing = int(request.form.get("spacing", 10))
        bg_color = request.form.get("bg_color", "#FFFFFF")  # Background color from UI
        margin_x = 10
        margin_y = 10
        horizontal_gap = 10
        a4_w, a4_h = 2480, 3508

        # Collect images and their copy counts
        images_data = []

        # Multi-image mode
        i = 0
        while f"image_{i}" in request.files:
            file = request.files[f"image_{i}"]
            copies = int(request.form.get(f"copies_{i}", 6))
            images_data.append((file.read(), copies))
            i += 1

        # Fallback to single image mode
        if not images_data and "image" in request.files:
            file = request.files["image"]
            copies = int(request.form.get("copies", 6))
            images_data.append((file.read(), copies))

        if not images_data:
            return "No image uploaded", 400

        print(f"DEBUG: Processing {len(images_data)} image(s)")

        # Process all images
        passport_images = []
        for idx, (img_bytes, copies) in enumerate(images_data):
            print(f"DEBUG: Processing image {idx + 1} with {copies} copies")
            try:
                img = process_single_image(img_bytes, bg_color=bg_color)
                img = img.resize((passport_width, passport_height), Image.LANCZOS)
                img = ImageOps.expand(img, border=border, fill="black")
                passport_images.append((img, copies))
            except ValueError as e:
                err_str = str(e)
                if "410" in err_str or "face" in err_str.lower():
                    return {"error": "face_detection_failed"}, 410
                elif "429" in err_str or "quota" in err_str.lower() or "402" in err_str or "insufficient_credits" in err_str.lower():
                    return {"error": "quota_exceeded"}, 429
                elif "403" in err_str or "auth_failed" in err_str.lower():
                    return {"error": "API Key is invalid or unauthorized."}, 500
                else:
                    print(f"ERROR processing image {idx}: {err_str}")
                    return {"error": err_str}, 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"server_error: {str(e)}"}, 500

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
                print(f"DEBUG: Placed at x={x}, y={y}")
                x += paste_w + horizontal_gap

        pages.append(current_page)
        print(f"DEBUG: Total pages = {len(pages)}")

        # Export multi-page PDF
        output = BytesIO()
        if len(pages) == 1:
            pages[0].save(output, format="PDF", dpi=(300, 300))
        else:
            pages[0].save(
                output,
                format="PDF",
                dpi=(300, 300),
                save_all=True,
                append_images=pages[1:],
            )
        output.seek(0)
        print("DEBUG: Returning PDF to client")

        return send_file(
            output,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="passport-sheet.pdf",
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"pdf_generation_failed: {str(e)}"}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)