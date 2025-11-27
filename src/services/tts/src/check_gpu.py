import torch
import subprocess
import shutil
import platform

print("=" * 60)
print("🔍 GPU & CUDA Environment Diagnostic")
print("=" * 60)

# ---- 1. Torch device check ----
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available:  {torch.cuda.is_available()}")
print(f"CUDA device count: {torch.cuda.device_count()}")
print()

if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        print(f"🟢 GPU {i}: {torch.cuda.get_device_name(i)}")
        print(f"    Memory: {torch.cuda.get_device_properties(i).total_memory / (1024 ** 3):.2f} GB")
        print(f"    Capability: {torch.cuda.get_device_capability(i)}")
else:
    print("⚠️  No GPU detected by PyTorch (using CPU mode).")

# ---- 2. System-level CUDA check ----
print("\nSystem CUDA toolchain:")
nvcc_path = shutil.which("nvcc")
if nvcc_path:
    try:
        output = subprocess.check_output(["nvcc", "--version"], text=True)
        print(output)
    except subprocess.CalledProcessError:
        print("⚠️  Error running nvcc.")
else:
    print("❌ nvcc not found (no CUDA toolkit in PATH)")

# ---- 3. Driver check (nvidia-smi) ----
if shutil.which("nvidia-smi"):
    print("\nGPU Driver (nvidia-smi):")
    subprocess.call(["nvidia-smi"])
else:
    print("\n❌ nvidia-smi not found — no NVIDIA driver detected or using non-NVIDIA GPU.")

# ---- 4. CPU fallback info ----
print("\nCPU info:")
print(platform.processor())

print("=" * 60)
print("✅ Check complete.")
print("=" * 60)
