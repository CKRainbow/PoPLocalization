import os
import json
import re

def get_translation_chars(folder_path):
    """
    统计指定文件夹下所有json文件中 'translation' 字段的非空字符集合。
    """
    all_chars = set()
    
    if not os.path.isdir(folder_path):
        print(f"错误: 文件夹 '{folder_path}' 不存在。")
        return all_chars

    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            filepath = os.path.join(folder_path, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and 'translation' in item and item['translation']:
                                # 提取所有非空白字符
                                non_whitespace_chars = ''.join(re.findall(r'\S', item['translation']))
                                all_chars.update(non_whitespace_chars)
            except json.JSONDecodeError:
                print(f"警告: 无法解析JSON文件: {filepath}")
            except Exception as e:
                print(f"处理文件时出错 {filepath}: {e}")
                
    return all_chars

if __name__ == '__main__':
    # 你可以在这里修改目标文件夹的路径
    target_folder = 'new'
    symbols_file = '3500+symbols.txt'
    output_filename = 'char_set.txt'

    # 从 new 文件夹中获取字符
    char_set = get_translation_chars(target_folder)
    
    # 读取 symbols 文件中的字符
    try:
        with open(symbols_file, 'r', encoding='utf-8') as f:
            symbol_chars = f.read()
            char_set.update(symbol_chars)
    except FileNotFoundError:
        print(f"警告: '{symbols_file}' 文件未找到。")
    except Exception as e:
        print(f"读取 '{symbols_file}' 时出错: {e}")

    if char_set:
        sorted_chars = sorted(list(char_set))
        
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write("".join(sorted_chars))
        
        print(f"合并后的字符集已保存到 '{output_filename}'。")
        print(f"总计 {len(sorted_chars)} 个独立字符。")
