import re

# The new maintenance modal block
new_block = """                <h1 class="text-3xl lg:text-4xl font-bold text-white mb-4 tracking-tight">System Updating</h1>
                <p class="text-gray-400 text-lg sm:text-xl max-w-md mx-auto mb-8 leading-relaxed">We're currently making things better. The application will be back online shortly.</p>
                
                <div class="bg-gray-800/60 border border-gray-700 backdrop-blur-md rounded-2xl p-6 shadow-2xl max-w-sm mx-auto transition-transform hover:scale-105 duration-300">
                  <div class="flex items-center gap-4 mb-4">
                     <div class="w-12 h-12 bg-blue-500/20 rounded-full flex items-center justify-center text-blue-400 text-xl font-bold border border-blue-500/30">
                       <i class="fa-solid fa-user-tie"></i>
                     </div>
                     <div class="text-left">
                       <p class="text-xs text-blue-400 font-semibold uppercase tracking-wider">Contact Administration</p>
                       <p class="text-white font-bold text-lg">Sanuwar Hussain</p>
                     </div>
                  </div>
                  <a href="mailto:sanuwarhussin88975@gmail.com" class="w-full bg-gray-700/50 hover:bg-gray-700 text-gray-300 hover:text-white py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 transition-colors border border-gray-600 font-medium text-sm">
                    <i class="fa-solid fa-envelope text-blue-400"></i> sanuwarhussin88975@gmail.com
                  </a>
                </div>
              </div>"""

def update_file(path):
    try:
        with open(path, 'r') as f:
            content = f.read()

        # Find the old block:
        # <h1 class="text-3xl font-bold text-white mb-4">Under Maintenance</h1>
        # <p class="text-gray-400 text-lg">The server is currently...
        # </div>
        
        pattern = r'<h1 class="text-3xl font-bold text-white mb-4">Under Maintenance</h1>\s*<p class="text-gray-400 text-lg">The server is currently down for maintenance\. We will be back shortly\.</p>\s*</div>'
        
        if re.search(pattern, content):
            content = re.sub(pattern, new_block, content)
            with open(path, 'w') as f:
                f.write(content)
            print(f"Updated {path}")
        else:
            print(f"Not found in {path}")
    except Exception as e:
        print(f"Failed {path}: {e}")

update_file('/Users/sanuwarhussain/Desktop/Work/instatnt photo source code/instant-photo/templates/index.html')
update_file('/Users/sanuwarhussain/Desktop/Work/instatnt photo source code/instant-photo/templates/check.js')
update_file('/Users/sanuwarhussain/Desktop/Work/instatnt photo source code/instant-photo/templates/check_js.html')
