from app import app
from flask import Flask, request, jsonify, send_file, redirect, url_for, render_template
from PIL import Image
import numpy as np
import cv2
import os
import json

print("Carregando main.py...")


# Pasta temporária para salvar imagens processadas
TEMP_DIR = "temp_images"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.route('/result')
def result():
    nni_filename = request.args.get('nni_filename')
    bi_filename = request.args.get('bi_filename')

    return render_template(
        'result.html',
        nni_url = url_for('download', filename=nni_filename),
        bi_url = url_for('download', filename=bi_filename))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    if 'image' not in request.files:
        return jsonify({'error': 'Nenhuma imagem foi enviada'}), 400
    
    image_file = request.files['image']
    image = np.array(Image.open(image_file))
    
    palette_size = request.form.get('paletteSize', type=int)
    if not palette_size:
        return jsonify({'error': 'Tamanho da paleta não enviado'}), 400
    
    if palette_size is None:
        return jsonify({'error': 'Parâmetro "paletteSize" é obrigatório'}), 400
    
    nni_image = nearest_neighbor_interpolation(image)
    bi_image = bilinear_interpolation(image)
    
    nni_quantized = quantize(nni_image, palette_size)
    bi_quantized = quantize(bi_image, palette_size)
    
    nni_path = os.path.join(TEMP_DIR, 'nni_quantized.jpg')
    bi_path = os.path.join(TEMP_DIR, 'bi_quantized.jpg')
    
    Image.fromarray(nni_quantized).save(nni_path)
    Image.fromarray(bi_quantized).save(bi_path)

    return redirect(url_for('result', nni_filename='nni_quantized.jpg', bi_filename='bi_quantized.jpg'))
    
@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    filepath = os.path.join(TEMP_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    else:
        return jsonify({'error': 'Arquivo não encontrado'}), 404    
       
# Algoritmo desenvolvido para a AP2.
# Interpolação por vizinho mais próximo.
def nearest_neighbor_interpolation(img, scale_factor=0.12):
    # Obtém as dimensões da imagem original
    height, width = img.shape[:2]

    # Calcula as novas dimensões
    new_height = int(height * scale_factor)
    new_width = int(width * scale_factor)

    # Cria uma nova matriz para a imagem redimensionada
    resized = np.zeros((new_height, new_width) + img.shape[2:], dtype=img.dtype)

    # Calcula a posição correspondente na imagem original para cada pixel da nova imagem
    for i in range(new_height):
        for j in range(new_width):
            orig_i = min(int(i / scale_factor), height - 1)
            orig_j = min(int(j / scale_factor), width - 1)
            resized[i, j] = img[orig_i, orig_j]
            
    # Retorna a imagem para o tamanho original mantendo o efeito pixelado
    final_image = np.zeros((height, width) + img.shape[2:], dtype=img.dtype)
    for i in range(height):
        for j in range(width):
            orig_i = min(int(i / (height / new_height)), new_height - 1)
            orig_j = min(int(j / (width / new_width)), new_width - 1)
            final_image[i, j] = resized[orig_i, orig_j]

    return final_image

# Algoritmo desenvolvido para a AP2
# Interpolação bilinear
def bilinear_interpolation(img, scale_factor=0.12):
    # Obtém as dimensões da imagem original
    height, width = img.shape[:2]

    # Calcula as novas dimensões
    new_height = int(height * scale_factor)
    new_width = int(width * scale_factor)

    # Cria uma nova matriz para a imagem redimensionada
    resized = np.zeros((new_height, new_width) + img.shape[2:], dtype=np.float32)

    # Calcula as coordenadas correspondentes na imagem original para cada pixel da nova imagem
    x = np.linspace(0, width - 1, new_width)
    y = np.linspace(0, height - 1, new_height)

    # Cria uma grade de coordenadas
    x, y = np.meshgrid(x, y)

    # Encontra os quatro vizinhos mais próximos
    x0 = np.floor(x).astype(int)
    x1 = np.minimum(x0 + 1, width - 1)
    y0 = np.floor(y).astype(int)
    y1 = np.minimum(y0 + 1, height - 1)

    # Calcula os pesos para cada vizinho
    wx = x - x0
    wy = y - y0

    # Realiza a interpolação bilinear
    for c in range(img.shape[2]):
        resized[..., c] = (
            (1 - wx) * (1 - wy) * img[y0, x0, c] +
            wx * (1 - wy) * img[y0, x1, c] +
            (1 - wx) * wy * img[y1, x0, c] +
            wx * wy * img[y1, x1, c]
        )

    # Converte de volta para uint8
    resized = np.clip(resized, 0, 255).astype(np.uint8)
    
    # Agora redimensiona de volta para o tamanho original, mantendo o estilo pixel-art
    final_resized = np.zeros_like(img)
    for i in range(img.shape[0]):
        for j in range(img.shape[1]):
            orig_i = min(int(i / (img.shape[0] / resized.shape[0])), resized.shape[0] - 1)
            orig_j = min(int(j / (img.shape[1] / resized.shape[1])), resized.shape[1] - 1)
            final_resized[i, j] = resized[orig_i, orig_j]

    # Retorna a imagem com efeito pixel-art
    return final_resized  

# Função para quantização da imagem
def quantize(img, palette_size):
    Z = img.reshape((-1, 3))
    Z = np.float32(Z)
    _, labels, centers = cv2.kmeans(Z, palette_size, None,
                                    criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
                                    attempts=10, flags=cv2.KMEANS_RANDOM_CENTERS)
    centers = np.uint8(centers)
    return centers[labels.flatten()].reshape(img.shape)

if __name__ == "__main__":
    print("Iniciando servidor...")
    app.run(host='127.0.0.1', port=5000)