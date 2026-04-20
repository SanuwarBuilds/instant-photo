import re

css_code = """
  <style>
    :root {
      --bg-dark: #0f172a;
      --bg-card: rgba(30, 41, 59, 0.6);
      --border-color: rgba(148, 163, 184, 0.1);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #3b82f6;
    }
    
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.1) 0%, transparent 20%),
        radial-gradient(circle at 90% 80%, rgba(168, 85, 247, 0.1) 0%, transparent 20%);
      color: var(--text-main);
      line-height: 1.6;
      min-height: 100vh;
    }

    header {
      background: rgba(15, 23, 42, 0.8);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-color);
      padding: 1.2rem 2rem;
      position: sticky;
      top: 0;
      z-index: 50;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      text-decoration: none;
      color: var(--text-main);
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: 0.5px;
    }

    .brand i {
      color: var(--accent);
      font-size: 1.5rem;
    }

    .nav-links {
      display: flex;
      gap: 1.5rem;
    }

    .nav-links a {
      color: var(--text-muted);
      text-decoration: none;
      font-size: 0.95rem;
      font-weight: 500;
      transition: color 0.2s ease;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }

    .nav-links a:hover {
      color: var(--text-main);
    }

    main {
      max-w-7xl;
      margin: 0 auto;
      padding: 3rem 2rem;
      max-width: 1200px;
    }

    .section-title {
      font-size: 2rem;
      font-weight: 800;
      margin-bottom: 2rem;
      text-align: center;
      background: linear-gradient(to right, #60a5fa, #c084fc);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 1.5rem;
    }

    .card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 1rem;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      backdrop-filter: blur(10px);
    }

    .card:hover {
      transform: translateY(-4px);
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3),
                  0 0 15px rgba(59, 130, 246, 0.15);
      border-color: rgba(59, 130, 246, 0.3);
    }

    .card-img-wrapper {
      position: relative;
      height: 180px;
      overflow: hidden;
      background: rgba(0,0,0,0.2);
    }

    .card-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.3s ease;
    }

    .card:hover .card-img {
      transform: scale(1.05);
    }

    .card-placeholder {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 4rem;
      color: rgba(255, 255, 255, 0.05);
      background: linear-gradient(135deg, rgba(30,41,59,1) 0%, rgba(15,23,42,1) 100%);
    }

    .card-content {
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      flex-grow: 1;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 0.75rem;
    }

    .card-title {
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--text-main);
      line-height: 1.3;
    }

    .card-version {
      background: rgba(59, 130, 246, 0.2);
      color: #93c5fd;
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
    }

    .card-desc {
      color: var(--text-muted);
      font-size: 0.95rem;
      flex-grow: 1;
      margin-bottom: 1.5rem;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .btn-download {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      background: var(--accent);
      color: white;
      text-decoration: none;
      padding: 0.75rem 1rem;
      border-radius: 0.5rem;
      font-weight: 600;
      font-size: 0.95rem;
      transition: background 0.2s ease;
      width: 100%;
      border: none;
      cursor: pointer;
    }

    .btn-download:hover {
      background: #2563eb;
    }
    
    /* Album Modal UI */
    .album-modal-overlay {
        position: fixed; inset: 0; background: rgba(0, 0, 0, 0.85);
        backdrop-filter: blur(8px); z-index: 1000;
        display: flex; align-items: center; justify-content: center;
        opacity: 0; pointer-events: none; transition: opacity 0.3s ease;
    }
    .album-modal-overlay.active { opacity: 1; pointer-events: auto; }
    
    .album-modal-content {
        background: #1e293b; width: 90%; max-width: 600px;
        border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        transform: scale(0.95); transition: transform 0.3s ease;
        display: flex; flex-direction: column; max-height: 85vh;
    }
    .album-modal-overlay.active .album-modal-content { transform: scale(1); }
    
    .album-modal-header {
        padding: 1rem 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);
        display: flex; justify-content: space-between; align-items: center;
    }
    .album-modal-body {
        padding: 1rem; overflow-y: auto; flex-grow: 1;
        display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
        gap: 0.75rem;
    }
    .album-item {
        background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.05);
        border-radius: 12px; overflow: hidden; display: flex; flex-direction: column;
    }
    .album-item img { width: 100%; height: 100px; object-fit: cover; }
    .album-close-btn { color: #94a3b8; font-size: 1.5rem; background: none; border: none; cursor: pointer; }

    /* Category Filters Swipable */
    .category-filters {
      display: flex;
      justify-content: flex-start;
      gap: 0.75rem;
      margin-bottom: 2rem;
      overflow-x: auto;
      padding-bottom: 0.5rem;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none; /* Firefox */
    }
    
    .category-filters::-webkit-scrollbar {
      display: none; /* Chrome/Safari */
    }
    
    .filter-btn {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      padding: 0.5rem 1.25rem;
      border-radius: 9999px;
      font-size: 0.9rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      white-space: nowrap;
    }
    
    .filter-btn:hover {
      background: rgba(255, 255, 255, 0.1);
      color: var(--text-main);
    }
    
    .filter-btn.active {
      background: rgba(59, 130, 246, 0.2);
      border-color: var(--accent);
      color: #93c5fd;
    }

    @media (max-width: 768px) {
      .grid { grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
      header { flex-direction: column; gap: 1rem; padding: 1rem; }
      .nav-links { width: 100%; justify-content: center; }
      .category-filters { margin-left: -1rem; margin-right: -1rem; padding: 0.5rem 1rem; }
    }
    @media (max-width: 480px) {
      .grid { grid-template-columns: 1fr; }
      main { padding: 2rem 1rem; }
      .category-filters { justify-content: flex-start; }
    }
  </style>
"""

modal_html = """
  <!-- Album Viewer Modal -->
  <div id="albumModal" class="album-modal-overlay">
      <div class="album-modal-content">
          <div class="album-modal-header">
              <h3 id="albumModalTitle" class="text-lg font-bold">Album View</h3>
              <button onclick="closeAlbumModal()" class="album-close-btn">&times;</button>
          </div>
          <div id="albumModalBody" class="album-modal-body">
              <!-- Dynamically populated -->
          </div>
      </div>
  </div>
"""

btn_logic = """
        let buttonHTML = '';
        if (item.is_album) {
            buttonHTML = `<button onclick="openAlbumModal('${item.id}')" class="btn-download" style="background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); width: 100%; border: none; cursor: pointer;">
              <i class="fa-solid fa-folder-open"></i> View Album (${item.album_files ? item.album_files.length : 0} files)
            </button>`;
        } else {
            buttonHTML = `<a href="${downloadLink}" class="btn-download" target="_blank" rel="noopener noreferrer">
              <i class="fa-solid fa-cloud-arrow-down"></i> Download Now
            </a>`;
        }
"""

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Replace Styles
    if '<style>' in content and '</style>' in content:
        content = re.sub(r'<style>.*?</style>', css_code.strip(), content, flags=re.DOTALL)

    # 2. Add Modal HTML before </body>
    if 'id="albumModal"' not in content:
        content = content.replace("</body>", modal_html + "\n</body>")
        
    # 3. Add Album Logic JS
    album_js = """
    function openAlbumModal(appId) {
        const item = allItems.find(x => x.id === appId);
        if (!item || !item.is_album) return;
        
        document.getElementById('albumModalTitle').textContent = item.title;
        const body = document.getElementById('albumModalBody');
        body.innerHTML = '';
        
        (item.album_files || []).forEach(f => {
            // Convert Cloudinary base URL to attachment URL for forced download
            let flink = f.link;
            if (flink.includes('res.cloudinary.com') && flink.includes('/upload/') && !flink.includes('fl_attachment')) {
                flink = flink.replace('/upload/', '/upload/fl_attachment/');
            }
            
            body.innerHTML += `
            <div class="album-item">
                <img src="${f.link}" alt="file" loading="lazy">
                <div style="padding: 8px; display: flex; flex-direction: column; flex-grow:1;">
                    <p style="font-size: 0.75rem; color: #cbd5e1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 8px;">${f.name}</p>
                    <a href="${flink}" target="_blank" style="background:#3b82f6; color:white; text-decoration:none; text-align:center; padding:6px; border-radius:6px; font-size:0.8rem; font-weight:bold; display:block; margin-top:auto;"><i class="fa-solid fa-download"></i> Download</a>
                </div>
            </div>
            `;
        });
        
        document.getElementById('albumModal').classList.add('active');
    }
    
    function closeAlbumModal() {
        document.getElementById('albumModal').classList.remove('active');
    }
    """
    if "function openAlbumModal" not in content:
        content = content.replace("</script>", album_js + "\n  </script>")

    # 4. Inject buttonHTML conditional safely
    # Check if we already injected btn_logic
    if "let buttonHTML = '';" not in content:
        # Find the render loop `const cardsHTML = items.map(item => {`
        # Insert `btn_logic` before `return \``
        content = re.sub(
            r"(const versionBadge.*?'';)",
            r"\1\n" + btn_logic,
            content,
            flags=re.DOTALL
        )
        # Now replace the actual anchor link inside the return string with `${buttonHTML}`
        content = re.sub(
            r'<a href="\$\{downloadLink\}".*?Download Now\s*</a>',
            r'${buttonHTML}',
            content,
            flags=re.DOTALL
        )

    with open(filepath, 'w') as f:
        f.write(content)
        
    print(f"Refactored {filepath}")

process_file('/Users/sanuwarhussain/Desktop/Work/instatnt photo source code/instant-photo/github-pages-app/index.html')
process_file('/Users/sanuwarhussain/Desktop/Work/instatnt photo source code/instant-photo/templates/downloads.html')
