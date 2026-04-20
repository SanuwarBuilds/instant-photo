js_code = """
    // --- Album Builder JS Logic ---
    let pendingAlbumFiles = [];
    const dragDropArea = document.getElementById('dragDropArea');
    const bulkFileInput = document.getElementById('bulkFileInput');
    const bulkUploadList = document.getElementById('bulkUploadList');
    
    dragDropArea.addEventListener('click', () => bulkFileInput.click());
    dragDropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dragDropArea.classList.add('border-blue-500', 'bg-blue-100');
    });
    dragDropArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragDropArea.classList.remove('border-blue-500', 'bg-blue-100');
    });
    dragDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dragDropArea.classList.remove('border-blue-500', 'bg-blue-100');
        if (e.dataTransfer.files.length) {
            handleSelectedFiles(e.dataTransfer.files);
        }
    });
    bulkFileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleSelectedFiles(e.target.files);
        }
    });

    function handleSelectedFiles(files) {
        for (let i = 0; i < files.length; i++) {
            pendingAlbumFiles.push(files[i]);
        }
        renderPendingFiles();
    }
    
    function renderPendingFiles() {
        bulkUploadList.innerHTML = '';
        pendingAlbumFiles.forEach((file, index) => {
            const div = document.createElement('div');
            div.className = "flex justify-between items-center bg-white p-3 rounded-lg border border-slate-200 shadow-sm";
            div.innerHTML = `
                <div class="flex items-center gap-3 overflow-hidden">
                   <div class="text-blue-500"><i class="fa-solid fa-file-image"></i></div>
                   <div class="truncate text-sm text-slate-700 font-medium">${file.name}</div>
                   <div class="text-xs text-slate-400">${(file.size / 1024 / 1024).toFixed(2)} MB</div>
                </div>
                <button onclick="removePendingFile(${index})" class="text-red-400 hover:text-red-600 bg-red-50 hover:bg-red-100 px-2 py-1 rounded transition-colors text-xs">Remove</button>
            `;
            bulkUploadList.appendChild(div);
        });
    }

    window.removePendingFile = function(index) {
        pendingAlbumFiles.splice(index, 1);
        renderPendingFiles();
    };

    window.publishAlbum = async function() {
        if (pendingAlbumFiles.length === 0) {
            alert("No files selected!");
            return;
        }
        
        const title = document.getElementById('albumTitleInput').value.trim();
        if (!title) {
            alert("Please enter a title for the album!");
            return;
        }

        const btn = document.querySelector('button[onclick="publishAlbum()"]');
        btn.disabled = true;
        btn.textContent = "Uploading...";
        
        document.getElementById('bulkUploadProgress').classList.remove('hidden');
        const progressBar = document.getElementById('bulkProgressBar');
        const progressText = document.getElementById('bulkProgressText');
        
        let uploadedFiles = [];
        let totalFiles = pendingAlbumFiles.length;

        try {
            for (let i = 0; i < totalFiles; i++) {
                let f = pendingAlbumFiles[i];
                progressText.textContent = `Uploading ${f.name} (${i + 1}/${totalFiles})...`;
                
                let b64 = await toBase64(f);
                let payload = {
                    file: b64,
                    filename: f.name,
                    service: 'cloudinary' // Or whichever default
                };

                let res = await fetch('/api/admin/upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!res.ok) {
                    let err = await res.json();
                    throw new Error(`Failed on ${f.name}: ` + (err.error || 'Server error'));
                }

                let dat = await res.json();
                uploadedFiles.push({
                    name: f.name,
                    link: dat.url
                });
                
                progressBar.style.width = Math.round(((i + 1) / totalFiles) * 100) + '%';
            }
            
            // Now create the App Entry
            progressText.textContent = `Finalizing Album...`;
            
            let coverImg = uploadedFiles.length > 0 ? uploadedFiles[0].link : "";
            
            const appRes = await fetch('/api/admin/store-apps', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: title,
                    description: `${totalFiles} items in this album.`,
                    category: "Albums",
                    version: "1.0",
                    image: coverImg,
                    is_album: true,
                    album_files: uploadedFiles
                })
            });
            
            if (!appRes.ok) throw new Error("Failed to create the Album App entry");
            
            alert(`Album "${title}" published successfully!`);
            
            // Trigger GitHub Deploy via backend endpoint
            await fetch('/api/admin/store-apps/sync', { method: 'POST' }).catch(() => {});
            
            // Reset
            pendingAlbumFiles = [];
            renderPendingFiles();
            document.getElementById('albumTitleInput').value = "";
            document.getElementById('bulkUploadProgress').classList.add('hidden');
            progressBar.style.width = '0%';
            loadStoreApps(); // refresh table
            
        } catch (err) {
            alert('Upload failed: ' + err.message);
        } finally {
            btn.disabled = false;
            btn.textContent = "Publish Album";
        }
    };

    function toBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
      });
    }
"""

with open('templates/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Append logic before closing script tag
if "let pendingAlbumFiles = [];" not in content:
    content = content.replace("</script>\n</body>", js_code + "\n</script>\n</body>")
    with open('templates/admin.html', 'w', encoding='utf-8') as f:
        f.write(content)
        print("JS Logic appended")
else:
    print("Logic already exists")
