# Session Prompts

Prompts used to create the webOS Update Server project.

---

## 1. Initial Exploration

> hi Claude, inside this folder is the restore utility for a legacy device, the HP TouchPad. The TouchPad ran an embedded-Linux based OS called webOS on an ARMv7 CPU. I would like you to unpack the utility, webosdoctorp305hstnhwifi.jar, get familiar with the OS, then let me know when you're ready to start a project.

---

## 2. Document Findings

> record what you've learned in a claude.md file

---

## 3. Research Update Mechanism

> webOS had an update mechanism -- an app on the launcher that would check Palm or HP servers for an update, then download and deploy it to the device. see if you can find it and learn how it worked.

---

## 4. Build the Server

> build a local update server replacement

*Clarifying questions answered:*
- Language preference: **Python/FastAPI**
- Testing device: **Has physical TouchPad**
- Compatibility level: **Full compatibility**
- Goal: **Deploy custom updates**

---

## 5. Write Plan

> write your plan to plan.md

---

## 6. Start Implementation

> start implementing the server

---

## 7. Create Test Package

> i moved device_patch to the parent folder. please generate a sample update package that when installed, creates a "UpdateApplied.txt" in /media/internal on the device.

---

## 8. Update Documentation

> update any docs so i can share this with others

---

## 9. Save Prompts

> save my prompts from this session to prompts.md
