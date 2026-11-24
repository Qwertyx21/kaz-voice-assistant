-- ==============================================================================
-- WirePlumber Bluetooth Audio Quality Preservation Policy
-- ==============================================================================
-- Problem:
-- When a microphone stream opens in Linux, WirePlumber by default automatically
-- switches connected Bluetooth earphones/headsets from high-fidelity stereo (A2DP)
-- to hands-free phone call mode (HSP/HFP, mono 16kHz/8kHz), causing music and
-- playback to sound muffled, tinny, and low-bitrate.
--
-- Solution:
-- Disabling 'media-role.use-headset-profile' prevents WirePlumber from auto-downgrading
-- your Bluetooth earphones. Your earbuds stay locked in High-Fidelity A2DP Stereo (SBC-XQ/AAC),
-- while microphone recording is handled cleanly via your laptop's internal microphone.
--
-- Installation:
-- 1. Create the user policy directory:
--    mkdir -p ~/.config/wireplumber/policy.lua.d
-- 2. Copy this file:
--    cp 11-bluetooth-policy.lua ~/.config/wireplumber/policy.lua.d/
-- 3. Restart WirePlumber:
--    systemctl --user restart wireplumber
-- ==============================================================================

bluetooth_policy = bluetooth_policy or {}
bluetooth_policy.policy = bluetooth_policy.policy or {}

-- Disable auto-switch to low-quality headset profile on active input streams
bluetooth_policy.policy["media-role.use-headset-profile"] = false
