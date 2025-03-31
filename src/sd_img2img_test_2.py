import os

# 建一個你有權限的 temp 資料夾
os.environ["TMPDIR"] = "/Users/syashinchen/Projects/DiscordChatBot/tmp"
os.makedirs(os.environ["TMPDIR"], exist_ok=True)
import random
import torch
import cv2
import numpy as np
from PIL import Image
from diffusers import StableDiffusionControlNetImg2ImgPipeline, ControlNetModel, EulerAncestralDiscreteScheduler

# --- 參數設定 ---
model_dir = "src/Models/Anything-v3-0-better-vae"  # 你的主模型資料夾（已轉成 diffusers 格式）
#model_dir = "src/meinaunreal_v5"
vae_path = "src/temp/orangemixvaeReupload_v10.pt"  # VAE 模型（需要轉換格式）
#vae_path = "src/meinaunreal_v5/kl-f8-anime2.safetensors"  # VAE 模型

negative_prompt = "easynegative"
prompt = "sketch,maltese dog,masterpiece,best quality,,<lora:ghibli:1>"
#seed = 2245550560
seed =  random.randint(0, 2**32 - 1)
guidance_scale = 7
steps = 20
width = 512
height = 512

def get_image_resized_info(image_path: str) -> tuple[str , Image.Image]:
    """
    根據圖片尺寸進行調整：
    - 若為正方形 → 調整為 512x512
    - 若為橫向長方形 → 寬調整為 768，等比例調整高
    - 若為縱向長方形 → 高調整為 768，等比例調整寬

    :param image_path: 圖片檔案路徑
    :param save_path: 儲存路徑（可選），若為 None 則覆蓋原圖
    :return: PIL.Image 物件
    """
    img = Image.open(image_path)
    w, h = img.size
    
    if w == h:
        new_size = (512, 512)
    elif w > h:
        new_w = 768
        new_h = int(h * (768 / w))
        new_size = (new_w, new_h)
    else:
        new_h = 768
        new_w = int(w * (768 / h))
        new_size = (new_w, new_h)
    
    # BICUBIC適合放大圖像
    # LANCZOS適合縮小圖像
    resized_img = img.resize(new_size, Image.LANCZOS)

    return img.filename.split('/')[-1], resized_img

# --- 載入原圖進行縮放 ---
info = get_image_resized_info("src/inputs/dog2.jpg")
init_image = info[1].convert("RGB")
init_image_name = info[0]

def get_canny_img(image_name: str):
    canny_path = f'src/results/{image_name}-canny.png'
    if os.path.exists(canny_path):
        return Image.open(canny_path)
    else: 
        # --- 利用 OpenCV 生成 Canny 邊緣圖 ---
        # 轉換成 numpy 陣列，並轉成灰階
        np_image = np.array(init_image)
        gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
        # 使用 Canny 偵測邊緣，這裡參數可依需求調整
        edges = cv2.Canny(gray, threshold1=100, threshold2=200)
        # 將邊緣圖轉回 RGB PIL Image
        control_image = Image.fromarray(cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB))
        control_image.save(canny_path)
        return control_image

control_image = get_canny_img(init_image_name)

# --- 載入 ControlNet 模型（以 Canny 為例） ---
# 請確保已下載 "lllyasviel/sd-controlnet-canny"
controlnet = ControlNetModel.from_pretrained(
    "lllyasviel/sd-controlnet-canny", torch_dtype=torch.float32
)

# --- 建立 ControlNet + img2img 管線 ---
pipe = StableDiffusionControlNetImg2ImgPipeline.from_pretrained(
    model_dir,
    controlnet=controlnet,
    torch_dtype=torch.float32,
    safety_checker=None
)

pipe = pipe.to("mps")  # 或 "cuda" 根據你的設備
pipe.enable_attention_slicing()

# --- 載入 LoRA 模型 ---
# pipe.load_lora_weights("src/temp/animeoutlineV4_16.safetensors", adapter_name="animeoutline")
#pipe.load_lora_weights("src/temp/OutlineSuperV9.safetensors", adapter_name="OutlineSuperV9")
pipe.load_lora_weights("src/temp/ghibli_style_offset.safetensors", adapter_name="ghibli")

pipe.set_adapters(["ghibli"])

# --- 設定採樣器 ---
pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
generator = torch.manual_seed(seed)

# --- 生成圖片 ---
# 注意這裡除了原圖 (image) 參數外，多了一個 control_image 參數
result = pipe(
    prompt=prompt,
    negative_prompt=negative_prompt,
    image=init_image,
    control_image=control_image,
    strength=0.7,         # 調整風格轉換程度，建議保留原圖結構可調低
    guidance_scale=guidance_scale,
    num_inference_steps=steps,
    generator=generator
).images[0]

result_path = f"src/results/{init_image_name}-result-{seed}.png"
result.save(result_path)
Image.open(result_path).show()
