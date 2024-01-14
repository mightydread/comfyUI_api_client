##param_assigner.py
from importlib.machinery import SourceFileLoader
import os

def load_key_mappings(key_mappings_file):
    if os.path.exists(key_mappings_file):
        key_mappings_module = SourceFileLoader("key_mappings", key_mappings_file).load_module()
        return key_mappings_module.key_mappings
    else:
        print(f"Error: Key mappings file '{key_mappings_file}' not found.")
        return {}

def find_seed_keys(key_mappings_file):
    key_mappings = load_key_mappings(key_mappings_file)
    seed_keys = [param_key for param_key in key_mappings.values() if "seed" in param_key]
    return seed_keys

def assign_params(prompt, params, key_mappings_file=None, overrides=None):
    if key_mappings_file:
        key_mappings = load_key_mappings(key_mappings_file)
    else:
        key_mappings = {}

    if key_mappings:
        for prompt_key, param_key in key_mappings.items():
            if param_key in overrides:
                # Override the specified parameter in params
                current_params = params
                keys = param_key.split('.')
                for k in keys[:-1]:
                    current_params = current_params[k]
                current_params[keys[-1]] = overrides[param_key]

            # Retrieve the value from params using the mapped key
            value = get_nested_value(params, param_key)

            # Assign the value to the corresponding prompt key
            set_nested_value(prompt, prompt_key, value)

def get_nested_value(dictionary, key):
    keys = key.split('.')
    value = dictionary
    for k in keys:
        value = value[k]
    return value

def set_nested_value(dictionary, key, value):
    keys = key.split('.')
    current_dict = dictionary
    for k in keys[:-1]:
        current_dict = current_dict.setdefault(k, {})
    current_dict[keys[-1]] = value

