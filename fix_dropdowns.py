import re

with open('gui/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Encuentra y reemplaza la sección del dropdown de estado
# Buscamos desde "canvas = tk.Canvas" hasta antes de "self._bind_dropdown_close"
new_lines = []
skip_until_bind = False
i = 0
while i < len(lines):
    line = lines[i]
    
    # Detectar inicio del canvas en saved_estado_dropdown
    if 'canvas = tk.Canvas(' in line and i > 1390 and i < 1420:
        # Saltar hasta encontrar self._bind_dropdown_close
        skip_until_bind = True
        i += 1
        # Agregar el nuevo código simple
        new_lines.append('        frame = tk.Frame(\n')
        new_lines.append('            self.saved_estado_dropdown,\n')
        new_lines.append('            width=180,\n')
        new_lines.append('            height=len(estados) * 28,\n')
        new_lines.append('            bg="#f1f5f9",\n')
        new_lines.append('            highlightthickness=1,\n')
        new_lines.append('            highlightbackground="#cbd5e1"\n')
        new_lines.append('        )\n')
        new_lines.append('        frame.pack(fill="both", expand=False)\n')
        new_lines.append('\n')
        new_lines.append('        for estado in estados:\n')
        new_lines.append('            btn = ctk.CTkButton(\n')
        new_lines.append('                frame,\n')
        new_lines.append('                text=estado,\n')
        new_lines.append('                width=170,\n')
        new_lines.append('                height=28,\n')
        new_lines.append('                fg_color="transparent",\n')
        new_lines.append('                hover_color="#e2e8f0",\n')
        new_lines.append('                text_color="#172033",\n')
        new_lines.append('                font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),\n')
        new_lines.append('                command=lambda v=estado: self._select_saved_estado_value(v)\n')
        new_lines.append('            )\n')
        new_lines.append('            btn.pack(pady=0, padx=1, fill="x")\n')
        continue
    
    if skip_until_bind:
        if 'self._bind_dropdown_close(self.saved_estado_dropdown' in line:
            skip_until_bind = False
            new_lines.append(line)
        i += 1
        continue
    
    new_lines.append(line)
    i += 1

with open('gui/app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Fixed saved_estado_dropdown')