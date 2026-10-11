; ScreenTool NSIS 安装脚本
; 安装后会在桌面和开始菜单创建快捷方式
; 模型文件与 EXE 同目录安装，OCR 可离线使用
;
; 构建方法：
;   1. 先运行 build_release.bat 生成 release/ 目录
;   2. 安装 NSIS: https://nsis.sourceforge.io/Download
;   3. 在 installer/ 目录运行: makensis ScreenTool.nsi
;   4. 生成的安装包在 installer\ 目录下

!include "MUI2.nsh"
!include "FileFunc.nsh"

; ── 基本信息 ──
Name "ScreenTool"
OutFile "ScreenTool_v2.3.0_Setup.exe"
InstallDir "$PROGRAMFILES64\ScreenTool"
InstallDirRegKey HKLM "Software\ScreenTool" "InstallDir"
RequestExecutionLevel admin

!define PRODUCT_NAME "ScreenTool"
!define PRODUCT_VERSION "2.3.0"
!define PRODUCT_PUBLISHER "Huang Xing"
!define PRODUCT_WEB_SITE "https://github.com/ScreenTool"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

; ── 界面设置 ──
!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\icon.ico"
!define MUI_UNICON "..\assets\icon.ico"

; 安装页面
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; 卸载页面
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ── 安装区段 ──
Section "ScreenTool (必须)" SecMain
    SectionIn RO
    SetOutPath "$INSTDIR"

    ; 主程序
    File "..\release\ScreenTool.exe"

    ; 模型文件（OCR 离线使用）
    SetOutPath "$INSTDIR\models\official_models\PP-OCRv6_medium_det_onnx"
    File "..\release\models\official_models\PP-OCRv6_medium_det_onnx\*.onnx"
    File "..\release\models\official_models\PP-OCRv6_medium_det_onnx\*.yml"
    File "..\release\models\official_models\PP-OCRv6_medium_det_onnx\*.json"

    SetOutPath "$INSTDIR\models\official_models\PP-OCRv6_medium_rec_onnx"
    File "..\release\models\official_models\PP-OCRv6_medium_rec_onnx\*.onnx"
    File "..\release\models\official_models\PP-OCRv6_medium_rec_onnx\*.yml"

    SetOutPath "$INSTDIR\models\official_models\UVDoc_onnx"
    File "..\release\models\official_models\UVDoc_onnx\*.onnx"
    File "..\release\models\official_models\UVDoc_onnx\*.yml"

    ; 注册表
    WriteRegStr HKLM "Software\ScreenTool" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME} ${PRODUCT_VERSION}"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\ScreenTool.exe"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"

    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$0"

    ; 卸载程序
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; 快捷方式
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\ScreenTool.lnk" "$INSTDIR\ScreenTool.exe"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\卸载 ScreenTool.lnk" "$INSTDIR\uninstall.exe"
    CreateShortCut "$DESKTOP\ScreenTool.lnk" "$INSTDIR\ScreenTool.exe"
SectionEnd

; ── 卸载区段 ──
Section "Uninstall"
    ; 删除文件和目录
    Delete "$INSTDIR\ScreenTool.exe"
    Delete "$INSTDIR\uninstall.exe"
    RMDir /r "$INSTDIR\models"
    RMDir "$INSTDIR"

    ; 删除快捷方式
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\ScreenTool.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\卸载 ScreenTool.lnk"
    RMDir "$SMPROGRAMS\${PRODUCT_NAME}"
    Delete "$DESKTOP\ScreenTool.lnk"

    ; 删除注册表
    DeleteRegKey HKLM "${PRODUCT_UNINST_KEY}"
    DeleteRegKey HKLM "Software\ScreenTool"
SectionEnd
