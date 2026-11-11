# VLC Media Player Configuration Guide

FrameShot-AI communicates with VLC Media Player using VLC's built-in HTTP control interface and native snapshot capabilities. Follow these steps to configure VLC.

---

## 1. Enable the Web Interface

1. Launch **VLC Media Player**.
2. From the top menu bar, click **Tools** → **Preferences** (or press `Ctrl + P`).
3. In the bottom-left corner under **Show settings**, select the **All** radio button (to view advanced settings).
4. In the left-hand navigation tree, click **Interface** → **Main interfaces**.
5. In the right panel, check the box for **Web** (`http`).

---

## 2. Set the Lua HTTP Password

1. Still in advanced preferences, expand **Main interfaces** in the left sidebar and click **Lua**.
2. In the right panel under **Lua HTTP**, find the **Password** field.
3. Enter your password. FrameShot-AI's default password is:
   ```
   frameshot
   ```
   *(If you choose a different password, update `vlc.password` in your `config.yaml` accordingly).*
4. Leave **Source directory** empty (uses VLC's default web files).

---

## 3. Configure the Video Snapshot Directory

FrameShot-AI captures video frames on pause to run vision detection. Configuring VLC's snapshot folder ensures instant frame captures:

1. In the left-hand navigation tree, click **Video**.
2. Scroll down to the **Video snapshots** section.
3. In **Directory**, enter or browse to FrameShot-AI's snapshots directory:
   ```
   C:\College\CODE\Projects\FrameShot-AI\data\snapshots
   ```
   *(Or relative to your FrameShot-AI install).*
4. In **Format**, ensure **PNG** or **JPG** is selected.
5. Click **Save** at the bottom of the Preferences dialog.

---

## 4. Restart VLC & Verify

1. **Close VLC completely** and launch it again for the interface changes to take effect.
2. Verify the HTTP interface is running by opening your web browser and visiting:
   ```
   http://127.0.0.1:8080/requests/status.json
   ```
3. A browser authentication prompt will appear:
   - **Username**: *(leave blank)*
   - **Password**: `frameshot` (or your configured password)
4. You should see a JSON payload detailing current playback status.

---

## 5. Verify from FrameShot-AI

Run the diagnostic tool in your terminal:

```powershell
python -m frameshot doctor
```

The output will confirm:
- `[PASS]` VLC binary detected
- `[PASS]` VLC HTTP interface reachable at `http://127.0.0.1:8080`
- `[PASS]` Subtitle and SQLite databases ready
- `[PASS]` YOLOv8 vision weights ready

---

## Troubleshooting

### HTTP 401 Unauthorized
- Double-check the password entered in VLC **Tools → Preferences (All) → Interface → Main interfaces → Lua → Password**.
- Make sure `vlc.password` in `config.yaml` matches exactly.

### Connection Refused (port 8080)
- Verify that VLC is currently open.
- Verify that **Web** interface is checked in **Interface → Main interfaces**.
- If port 8080 is used by another program, change the port in VLC (**Interface → Main interfaces → Lua → HTTP port**) to `8085` and update `vlc.port: 8085` in `config.yaml`.

