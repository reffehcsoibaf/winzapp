# Como publicar uma release estável do WinZapp (manual, sem gh CLI)

Processo 100% manual: build local, assinatura local, upload pela página do
GitHub. Não passa pelo GitHub Actions (sem suíte de testes automática nem
checagem de ordem alpha/stable) — é a troca por não depender do `gh` CLI.

Sempre no **cmd** (Prompt de Comando), na pasta do repositório.

## Antes de começar

- Decida o número da próxima versão (ex.: `1.1.3.0`). Regra: sempre subir pelo
  menos o terceiro número (patch) em diante — nunca só o último.
- Tenha em mãos a senha (passphrase) da chave de assinatura.

## Passo a passo

**1. Atualizar a versão antes de compilar** (troque `1.1.3.0` pela versão da vez):

```cmd
cd C:\github\winzapp
echo __version__ = "1.1.3.0" > client\version.py
```

**2. Compilar.** Pule a linha do `setup_api.py` se `client\api\dist\server.js`
e `client\node\` já existirem e estiverem atualizados:

```cmd
venv\Scripts\python.exe setup_api.py
venv\Scripts\python.exe build.py
```

Gera `dist\WinZappInstaller.exe` e `dist\WinZapp.zip`.

**3. Gerar o SHA256SUMS.txt** (mesma versão do passo 1, sem o `v` na frente):

```cmd
generate_sha256sums.bat 1.1.3.0
```

Confere se o arquivo mostrado no final tem 3 linhas: a de versão e as duas de
hash. Esse `.bat` está em `C:\github\winzapp\generate_sha256sums.bat` — não
precisa alterar nada nele entre uma release e outra, só passar a versão certa
como argumento.

**4. Assinar** (com o `v` na frente, igual ao nome da tag):

```cmd
python sign_release_manual.py dist\SHA256SUMS.txt v1.1.3.0 --key C:\WinZappKeys\stable-primary.pem
```

Digita a senha da chave quando pedir. Gera `dist\SHA256SUMS.txt.sig`.

**5. Commitar a versão:**

```cmd
git add client\version.py
git commit -m "chore: bump version to v1.1.3.0"
git push origin main
```

**6. Publicar pela página do GitHub:**

1. Vá em **Releases** → **Draft a new release**.
2. Em "Choose a tag", digite `v1.1.3.0` (nova tag, vai apontar pro `main`
   que você acabou de enviar).
3. Título: `v1.1.3.0`.
4. Descrição: cole o changelog dessa versão, se quiser.
5. Arraste os **4 arquivos** de `dist\` pra área de anexos:
   `WinZappInstaller.exe`, `WinZapp.zip`, `SHA256SUMS.txt`, `SHA256SUMS.txt.sig`.
6. Clique **Publish release**.

## Se algo der errado

Roda o comando que falhou salvando a saída, e me manda o arquivo:

```cmd
<comando que falhou> > erro.txt 2>&1
```
