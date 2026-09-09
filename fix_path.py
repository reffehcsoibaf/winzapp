"""
Restaura o PATH do usuário a partir do backup salvo, e adiciona a pasta do
MSYS2 (gcc/windres) no final — sem o limite de 1024 caracteres do comando
`setx`, que corrompeu o PATH original.
"""
import os
import winreg

backup_path = os.path.join(os.environ["USERPROFILE"], "path_backup.txt")

with open(backup_path, "r", encoding="utf-8") as f:
    original_path = f.read().strip()

msys2_bin = r"C:\msys64\ucrt64\bin"

if msys2_bin.lower() in original_path.lower():
    print("A pasta do MSYS2 já está no backup — nada a adicionar.")
    new_path = original_path
else:
    new_path = original_path + ";" + msys2_bin

key = winreg.OpenKey(
    winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
)
winreg.SetValueEx(key, "PATH", 0, winreg.REG_SZ, new_path)
winreg.CloseKey(key)

print(f"PATH restaurado e atualizado com sucesso. Tamanho final: {len(new_path)} caracteres.")
print("Feche esta janela e abra uma nova para o novo PATH ter efeito.")
