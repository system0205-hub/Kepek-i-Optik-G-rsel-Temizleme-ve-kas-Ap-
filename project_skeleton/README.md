# Project Skeleton

Bu klasor yeni projelerde standart dokumanlari tek komutla olusturmak icin kullanilir.

## Olusturulan dosyalar
- `agent.md`
- `todo.md`
- `architecture.md`
- `knowledge.md`

## Hizli kullanim
PowerShell:

```powershell
.\project_skeleton\init_project.ps1
```

Belirli klasore kurulum:

```powershell
.\project_skeleton\init_project.ps1 -TargetPath "C:\path\to\new-project"
```

Var olan dosyalari ezmek icin:

```powershell
.\project_skeleton\init_project.ps1 -Force
```
