# Build Checklist - EthernetIP Virtual PLC Simulator

## Pre-Build Verification

### Phase 1: Pillow Replacement (Complete)
- [x] Pillow removed from requirements.txt
- [x] Pillow removed from main.py REQUIRED_PACKAGES
- [x] screenshot_manager.py uses Qt native (QPixmap)
- [x] annotation_canvas.py accepts QPixmap
- [x] feedback_dialog.py has no PIL imports

### Phase 2: Code Cleanup (Complete)
- [x] Dead code removed (~184 lines)
  - [x] feedback_service.py unused methods removed
  - [x] feedback_repository.py unused methods removed
  - [x] screenshot_manager.py unused methods removed
  - [x] tag_service.py search_tags() removed
  - [x] tag_repository.py update_value() removed
- [x] INTEGER_TYPES constant added to data_types.py

### Phase 3: PyInstaller Configuration (Complete)
- [x] EthernetIP_Simulator.spec created
- [x] build_exe.bat script created
- [x] main_frozen.py simplified entry point created

### Phase 4: Environment Setup
- [ ] Python 3.9+ installed
- [ ] Virtual environment activated (recommended)
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] PyInstaller installed: `pip install pyinstaller`
- [ ] UPX downloaded and in PATH
  - Download: https://github.com/upx/upx/releases
  - Extract upx.exe to a folder in your PATH (e.g., C:\Windows\System32)

---

## Build Steps

### 1. Pre-Build Test
- [ ] Run application normally to verify it works:
  ```bash
  python main.py
  ```
- [ ] Test screenshot feature (F12) - verify Qt native works
- [ ] Create/edit/delete tags
- [ ] Start/stop server

### 2. Build Executable
- [ ] Run build script:
  ```bash
  build_exe.bat
  ```
- [ ] Wait for build to complete (may take 2-5 minutes)
- [ ] Check for errors in output

### 3. Verify Build Size
- [ ] Check exe size: `dist\EthernetIP_Simulator.exe`
- [ ] **Target: < 120 MB** (ideal: 80-100 MB)
- [ ] If size > 120 MB, see "Advanced Optimizations" section below

---

## Post-Build Testing

### Functional Tests
Run these tests on the built .exe:

- [ ] **Launch Test**
  - [ ] No console window appears
  - [ ] Application starts < 3 seconds
  - [ ] Main window displays correctly

- [ ] **Tag Management**
  - [ ] Create new tags (DINT, BOOL, REAL, STRING, arrays)
  - [ ] Edit tag descriptions (Ctrl+E)
  - [ ] Edit tag values (double-click)
  - [ ] Delete tags

- [ ] **Server Operations**
  - [ ] Start server (F5)
  - [ ] Server status shows "Running"
  - [ ] Stop server (F6)
  - [ ] Change IP/Port settings (F8)

- [ ] **Screenshot/Feedback (Qt Native)**
  - [ ] Press F12
  - [ ] Screenshot captures correctly
  - [ ] Annotation tools work (rectangle, arrow, pen, circle)
  - [ ] Submit feedback saves annotated screenshot
  - [ ] **CRITICAL:** No Pillow errors in logs

- [ ] **Logs Tab**
  - [ ] Switch to Logs tab (Ctrl+2)
  - [ ] Logs display in real-time
  - [ ] Filter by level works
  - [ ] Clear and Save buttons work

- [ ] **Database Persistence**
  - [ ] Create tags and close app
  - [ ] Reopen app - tags still exist
  - [ ] Database file created in data/ folder

- [ ] **Memory Usage**
  - [ ] Check Task Manager
  - [ ] Memory usage < 150 MB at idle

### Clean Machine Test
- [ ] Copy .exe to machine WITHOUT Python installed
- [ ] Run .exe - should work standalone
- [ ] All features functional

---

## Size Analysis

### If Build > 120 MB

1. **Analyze contents:**
   ```bash
   pyi-archive_viewer dist\EthernetIP_Simulator.exe
   ```

2. **Check for bloat:**
   - Type `list` to see all bundled files
   - Look for unexpected large files
   - Common culprits: Qt plugins, unused DLLs

3. **Advanced Optimization Options:**

   **Option A: One-Folder Mode** (20-30% smaller)
   - Edit .spec file: Change `exclude_binaries=True` in EXE section
   - Add COLLECT section (see plan)
   - Distribute as folder instead of single file

   **Option B: Filter Qt Plugins** (5-10 MB saved)
   - Edit .spec file Analysis section:
   ```python
   a.binaries = [x for x in a.binaries if not (
       'qt' in x[0].lower() and
       any(p in x[0].lower() for p in ['xcb', 'wayland', 'eglfs'])
   )]
   ```

   **Option C: Disable UPX** (if antivirus issues)
   - Edit .spec: Set `upx=False`
   - Size will increase but may avoid false positives

---

## Common Issues & Solutions

### "UPX not found"
- Download UPX from https://github.com/upx/upx/releases
- Extract upx.exe to C:\Windows\System32 or add to PATH
- Re-run build script

### "PyInstaller command not found"
- Install: `pip install pyinstaller`
- Ensure you're in virtual environment if using one

### "Module not found" errors
- Check all dependencies installed: `pip install -r requirements.txt`
- Verify cpppo and PySide6 are installed

### Antivirus False Positive
- UPX compression can trigger false positives
- Solution 1: Add exception in antivirus
- Solution 2: Build without UPX (set `upx=False` in .spec)
- Solution 3: Sign the executable (advanced)

### Screenshot Feature Not Working
- Verify Pillow completely removed
- Check imports in screenshot_manager.py (should use PySide6.QtGui)
- Check logs for PIL/Pillow errors

### Build Size Too Large (> 150 MB)
- Ensure all Phase 1-3 changes completed
- Verify .spec excludes list is correct
- Try one-folder mode instead of one-file
- Consider removing more PySide6 modules (test carefully)

---

## Success Criteria

### Primary Goals
- ✓ Final .exe size < 120 MB (target: 80-100 MB)
- ✓ All core features functional (EthernetIP server + full GUI)
- ✓ Startup time < 3 seconds
- ✓ No external dependencies required
- ✓ Works on clean Windows machine (no Python)

### Secondary Goals
- ✓ One-click build process (build_exe.bat)
- ✓ Cleaner codebase (~184 lines removed)
- ✓ Qt native screenshot (no Pillow dependency)

### Stretch Goals
- Final size < 80 MB
- Startup time < 2 seconds
- Portable ZIP package < 80 MB

---

## Final Steps

### After Successful Build
1. [ ] Test all features on development machine
2. [ ] Test on clean machine (no Python)
3. [ ] Document final .exe size in README.md
4. [ ] Create portable ZIP package:
   ```
   dist/
     EthernetIP_Simulator.exe
     README.md (usage instructions)
     data/ (optional - will be created on first run)
   ```
5. [ ] Update README.md with build instructions
6. [ ] Consider creating installer (optional - Inno Setup, NSIS)

### Distribution Checklist
- [ ] .exe tested and working
- [ ] Size documented
- [ ] Usage instructions written
- [ ] System requirements documented (Windows 10+ 64-bit)
- [ ] Note about antivirus if UPX used
- [ ] Release notes created

---

## Build Information Template

After successful build, document:

```
Build Date: _______________
Build Size: _______ MB
UPX Compression: Yes / No
Startup Time: _______ seconds
Memory at Idle: _______ MB
Tested on Windows Version: _______________
```

## Notes

- Keep this checklist updated as you discover issues
- Document any deviations from the plan
- Save build logs for troubleshooting
