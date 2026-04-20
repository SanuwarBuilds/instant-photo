import re

def rewrite():
    try:
        with open('templates/admin.html', 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Colors replacement
        replacements = [
            ("background-color: #0f172a;", "background-color: #f1f5f9;"),
            ("color: #f8fafc;", "color: #0f172a;"),
            ("bg-gray-800", "bg-white"),
            ("bg-gray-900", "bg-slate-50"),
            ("border-gray-800", "border-slate-200"),
            ("border-gray-700", "border-slate-200"),
            ("text-gray-400", "text-slate-500"),
            ("text-gray-300", "text-slate-600"),
            ("text-white", "text-slate-900"),
            ("glass-card", "glass-card bg-white border border-slate-200 shadow-sm"),
            ("bg-slate-900/40", "bg-slate-500/40"),
            ('class="divide-y divide-gray-800"', 'class="divide-y divide-slate-200"'),
            ('class="bg-gray-900/50"', 'class="bg-slate-50"')
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)

        # Fix glass card css
        content = content.replace(
            ".glass-card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.05); }",
            ".glass-card { background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(12px); border: 1px solid rgba(0, 0, 0, 0.05); }"
        )

        # 2. Wrap Tables in Mobile Scrollers
        # Table 1: API Keys
        if '<div id="keysTableBody"' in content and '<div class="w-full overflow-x-auto">' not in content:
            content = re.sub(
                r'(<h2 class="text-xl font-bold mb-4">API Keys.*?)(<div id="keysTableBody".*?</div>\s*</div>)',
                r'\1<div class="w-full overflow-x-auto">\2</div>',
                content, flags=re.DOTALL
            )
            
        # Table 2: Countdowns
        content = re.sub(
            r'(<div id="countdownsTableBody")',
            r'<div class="w-full overflow-x-auto border-b border-t border-slate-200">\1',
            content
        )
        # Assuming div closing tags are matched, we will just wrap the inner div
        # Actually a safer way is to add min-w to the flex cols
        content = content.replace('class="divide-y divide-slate-200 flex flex-col"', 'class="divide-y divide-slate-200 flex flex-col min-w-[600px]"')

        # 3. Add Bulk Upload Component UI
        bulk_ui = """
      <!-- Album Builder / Bulk Uploader -->
      <div class="glass-card rounded-2xl shadow-sm border border-slate-200 overflow-hidden mt-8">
        <div class="p-6 border-b border-slate-200 bg-slate-50 flex justify-between items-center flex-wrap gap-4">
          <div>
            <h2 class="text-xl font-bold text-slate-900">Bulk Album Builder</h2>
            <p class="text-sm text-slate-500 mt-1">Drag and drop multiple photos to create a grouped album in one click.</p>
          </div>
          <div class="flex gap-2 w-full sm:w-auto">
            <input type="text" id="albumTitleInput" placeholder="Album Title (e.g. Wedding Event)" class="px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm w-full sm:w-64 focus:ring-2 focus:ring-blue-500">
            <button onclick="publishAlbum()" class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg whitespace-nowrap">Publish Album</button>
          </div>
        </div>
        <div class="p-6 space-y-4">
          <div id="dragDropArea" class="border-2 border-dashed border-blue-300 bg-blue-50 rounded-xl p-8 text-center cursor-pointer hover:bg-blue-100 transition-colors">
            <i class="fa-solid fa-cloud-arrow-up text-3xl text-blue-500 mb-2"></i>
            <p class="text-slate-600 font-medium">Drag & Drop files here or click to browse</p>
            <input type="file" id="bulkFileInput" multiple class="hidden" accept="image/*,.zip,.apk">
          </div>
          
          <div id="bulkUploadList" class="space-y-2 max-h-[300px] overflow-y-auto pr-2">
            <!-- Files appear here -->
          </div>
          
          <div id="bulkUploadProgress" class="hidden">
             <div class="w-full bg-slate-200 rounded-full h-2 mt-4">
               <div id="bulkProgressBar" class="bg-blue-500 h-2 rounded-full" style="width: 0%"></div>
             </div>
             <p id="bulkProgressText" class="text-xs text-slate-500 text-center mt-1">Uploading 0/0 files...</p>
          </div>
        </div>
      </div>
"""
        # Inject right before Add App Modal
        if "<!-- Add App Modal -->" in content and "bulkFileInput" not in content:
            content = content.replace("<!-- Add App Modal -->", bulk_ui + "\n\n  <!-- Add App Modal -->")
            
        with open('templates/admin.html', 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("Updated templates/admin.html")
    except Exception as e:
        print(f"Error: {e}")

rewrite()
