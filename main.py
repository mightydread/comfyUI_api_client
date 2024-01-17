## main.py
import websocket
import json
import os
import uuid
import requests
import argparse
import param_assigner
import random
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

def read_json_file(file_path):
    with open(file_path) as f:
        return json.load(f)

parser = argparse.ArgumentParser(description='Generate images based on expressions.')
parser.add_argument('-m', '--mode', choices=['single', 'multiple'], default='single',
                    help='Select the mode: single (default) or multiple')
parser.add_argument('-e', '--expressions', default='',
                    help='Comma-separated list of expressions to generate images')
parser.add_argument('-r', '--random', action='store_true',
                    help='Random seed')
parser.add_argument('-x', '--param-overrides', default='',
                    help='Override specific parameters in params.json. Specify as key=value pairs separated by commas.')
parser.add_argument('-i', '--input-folder', default='./',
                    help='Path to folder containing the input files')
parser.add_argument('-o','--output-folder', default='output_images',
                    help='Path to output folder')
parser.add_argument('-p', '--params-file', default='params.json',
                    help='Path to the params JSON file')
parser.add_argument('-w', '--workflow-api-file', default='workflow_api.json',
                    help='Path to the workflow API JSON file')
parser.add_argument('-k', '--key-mappings', default='key_mappings.py',
                    help='Provide a file containing key mappings for parameter assignments')
parser.add_argument('--server-address', default='127.0.0.1',
                    help='Server address of the ComfyUI server')
parser.add_argument('--server-port', default='8188',
                    help='Port of the ComfyUI server')
parser.add_argument('--server-protocol',choices=['http', 'https'], default='http',
                    help='Protocol to use to connect: http (default) or https')
args = parser.parse_args()
SERVER_ADDRESS = args.server_address
PORT = args.server_port
PROTOCOL = args.server_protocol
base_url = f"{PROTOCOL}://{SERVER_ADDRESS}:{PORT}"
CLIENT_ID = str(uuid.uuid4())
OUTPUT_FOLDER = args.output_folder
PARAM_FILE = os.path.join(args.input_folder, args.params_file)
PROMPT_FILE = os.path.join(args.input_folder, args.workflow_api_file)
KEYMAP_FILE = os.path.join(args.input_folder, args.key_mappings)
params = read_json_file(PARAM_FILE)
prompt = read_json_file(PROMPT_FILE)
key_mappings_file = KEYMAP_FILE




def make_request(url, method='POST', data=None, params=None):
    response = requests.request(method, url, json=data, params=params)
    response.raise_for_status()
    try:
        return response.json()
    except json.decoder.JSONDecodeError:
        return response.content

def queue_prompt(prompt):
    url = f"{base_url}/prompt"
    return make_request(url, method='POST', data={"prompt": prompt, "client_id": CLIENT_ID})

def get_image(filename, subfolder, folder_type):
    url = f"{base_url}/view"
    params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    return make_request(url, method='GET', params=params)

def get_history(prompt_id):
    url = f"{base_url}/history/{prompt_id}"
    return make_request(url, 'GET')

def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}

    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # Execution is done
        else:
            continue  # Previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for node_id, node_output in history['outputs'].items():
        if 'images' in node_output:
            images_output = []
            for image in node_output['images']:
                image_data = get_image(image['filename'], image['subfolder'], image['type'])
                images_output.append(image_data)
            output_images[node_id] = images_output

    return output_images

def save_image(image_data, output_path):
    with open(output_path, "wb") as image_file:
        image_file.write(image_data)

def save_generated_images(images, params, prompt):
    # Dynamic output directory
    output_directory = os.path.join(OUTPUT_FOLDER)
    if "character" in params:
        output_directory = os.path.join(output_directory, params["character"])
    if "outfit_folder" in params:
        output_directory = os.path.join(output_directory, params["outfit_folder"])
    os.makedirs(output_directory, exist_ok=True)

    for node_id, images_output in images.items():
        for index, image_data in enumerate(images_output):
            if "expression" in params:
                expression = params["expression"]
            else:
                expression = ""
            node_title = prompt[node_id]["_meta"]["title"]
            seed = params["seed"]
            image_filename = f"{expression}_{node_title}_{seed}_{index}.png"
            output_path = os.path.join(output_directory, image_filename)
            save_image(image_data, output_path)

def generate_simple(ws, params, prompt, overrides=None):
    param_assigner.assign_params(prompt, params, key_mappings_file, overrides)
    images = get_images(ws, prompt)
    save_generated_images(images, params, prompt)

def generate_images_for_expressions(ws, params, prompt, expressions, overrides=None):
    for expression in expressions:
        params["expression"] = expression
        param_assigner.assign_params(prompt, params, key_mappings_file, overrides)
        generate_simple(ws, params, prompt, overrides)


def main():
    ws = websocket.WebSocket()
    try:
        ws.connect(f"ws://{SERVER_ADDRESS}:{PORT}/ws?clientId={CLIENT_ID}")
    except Exception as e:
        logging.error(f"WebSocket connection failed: {e}")

    overrides = {}
    if args.param_overrides:
        overrides = {item.split('=')[0]: item.split('=')[1] for item in args.param_overrides.split(',')}
    if args.random:
        seed_keys = param_assigner.find_seed_keys(key_mappings_file)
        for seed_key in seed_keys:
            overrides[seed_key] = random.randint(1, 1125899906842624)
            logging.info(f"{seed_key}:{overrides[seed_key]}")
    if args.mode == 'multiple':
        if args.expressions:
            expression_list = [expr.strip() for expr in args.expressions.split(',')]
            generate_images_for_expressions(ws, params, prompt, expression_list, overrides)
        else:
            logging.error("Please provide a list of expressions using --expressions.")
    else:
        generate_simple(ws, params, prompt, overrides)


    ws.close()

if __name__ == "__main__":
    main()
