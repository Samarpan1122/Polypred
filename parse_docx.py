import zipfile
import re
import os
import json

with zipfile.ZipFile('LSTM_SI.docx') as z:
    xml_content = z.read('word/document.xml').decode('utf-8')
    rels_content = z.read('word/_rels/document.xml.rels').decode('utf-8')

# parse rels
rels = {}
for match in re.finditer(r'Id="(rId\d+)".*?Target="media/(image\d+\.\w+)"', rels_content):
    rels[match.group(1)] = match.group(2)

# Very crude parse of document.xml to find text vs images
parts = []
# split by paragraphs <w:p>
for p in xml_content.split('<w:p '):
    # find text
    texts = re.findall(r'<w:t(?: xml:space="preserve")?>(.*?)</w:t>', p)
    text = "".join(texts).strip()
    
    # find images
    imgs = re.findall(r'r:embed="(rId\d+)"', p)
    
    if text:
        parts.append({"type": "text", "val": text})
    for img in imgs:
        if img in rels:
            parts.append({"type": "image", "val": rels[img]})

current_model = "Unknown"
model_images = {"standalone_lstm": [], "lstm_bayesian": [], "lstm_siamese_bayesian": [], "siamese_lstm": [], "Unknown": []}

for p in parts:
    if p["type"] == "text":
        t = p["val"].lower().replace('+', ' ')
        if "siamese" in t and "lstm" in t and "bayesian" in t:
            current_model = "lstm_siamese_bayesian"
        elif "siamese" in t and "lstm" in t:
            current_model = "siamese_lstm"
        elif "lstm" in t and "bayesian" in t:
            current_model = "lstm_bayesian"
        elif "lstm" in t:
            current_model = "standalone_lstm"
    elif p["type"] == "image":
        if current_model in model_images:
            model_images[current_model].append(p["val"])
        else:
            model_images["Unknown"].append(p["val"])

print(json.dumps(model_images, indent=2))
