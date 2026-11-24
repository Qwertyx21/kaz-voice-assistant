# Realtek ALC256 Microphone Noise Fix (ASUS VivoBook / Linux Laptops)

### The Issue
On many ASUS laptops (such as ASUS VivoBook 14 X407UAR with Realtek ALC256 codec, PCI ID `1043:166e`), Linux kernel drivers mistakenly leave ungrounded floating pins active (e.g. pins `0x12`, `0x13`, and `0x1a`), while routing the internal analog microphone to the wrong pin without proper bias voltage. This results in deafening +60dB static hiss/white noise and no audible voice pickup.

### The Fix
1. **Disable floating dummy pins:** Set pins `0x12`, `0x13`, `0x1a` to disabled state (`0x411111f0`).
2. **Assign physical internal mic pin:** Pin `0x1b` configured with VREF bias voltage (`0x90a70130`).
3. **Assign headset mic pin:** Pin `0x19` configured as headset mic (`0x04a11120`).
4. **Driver option:** Set `model=alc256-asus-headset` in modprobe.

### Installation
```bash
# 1. Copy firmware patch verb file
sudo cp asus-alc256-mic.fw /lib/firmware/

# 2. Copy modprobe options configuration
sudo cp asus-alc256-mic.conf /etc/modprobe.d/

# 3. Rebuild initramfs and reboot
sudo update-initramfs -u
sudo reboot
```

After rebooting, calibrate mixer levels:
```bash
amixer -c 0 sset "Internal Mic Boost" 1    # +10dB clean boost
amixer -c 0 sset "Capture" 60%            # +11.25dB capture
```
