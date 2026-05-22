import re

with open('gui/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Función para reemplazar canvas por frame en dropdowns
def replace_canvas_with_frame(content, dropdown_name):
    # Patrón más flexible
    lines = content.split('\n')
    result = []
    i = 0
    skip = False
    in_target = False
    
    while i < len(lines):
        line = lines[i]
        
        # Detectar si estamos en el dropdown correcto
        if f'self.{dropdown_name}_dropdown = ctk.CTkToplevel(self)' in line:
            in_target = True
            result.append(line)
            i += 1
            continue
            
        if in_target:
            # Cuando vemos canvas = tk.Canvas, es el momento de reemplazar
            if 'canvas = tk.Canvas(' in line:
                skip = True
                # Insertar frame simple
                result.append('        frame = tk.Frame(')
                result.append(f'            self.{dropdown_name}_dropdown,')
                result.append('            width=180,')
                result.append('            height=len(estados) * 28,')
                result.append('            bg="#f1f5f9",')
                result.append('            highlightthickness=1,')
                result.append('            highlightbackground="#cbd5e1"')
                result.append('        )')
                result.append('        frame.pack(fill="both", expand=False)')
                result.append('')
                result.append('        for estado in estados:')
                result.append('            btn = ctk.CTkButton(')
                result.append('                frame,')
                result.append('                text=estado,')
                result.append('                width=170,')
                result.append('                height=28,')
                result.append('                fg_color="transparent",')
                result.append('                hover_color="#e2e8f0",')
                result.append('                text_color="#172033",')
                result.append('                font=ctk.CTkFont(family=self.font_family, size=13, weight="bold"),')
                result.append(f'                command=lambda v=estado: self._select_{dropdown_name}_value(v)')
                result.append('            )')
                result.append('            btn.pack(pady=0, padx=1, fill="x")')
                i += 1
                continue
            
            # Saltar hasta el bind
            if skip:
                if 'self._bind_dropdown_close(self.' in line and dropdown_name in line:
                    skip = False
                    in_target = False
                    result.append(line)
                i += 1
                continue
        
        result.append(line)
        i += 1
    
    return '\n'.join(result)

# Aplicar a add_estado
content = replace_canvas_with_frame(content, 'add_estado')

with open('gui/app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed dropdowns')