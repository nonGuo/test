# -*- coding: utf-8 -*-
"""
API 服务测试脚本

测试场景:
1. 健康检查
2. 生成测试设计
3. 下载 XMind 文件
"""
import os
import sys
import requests
import time
from pathlib import Path

# 配置
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5000')
TEST_FILES_DIR = os.getenv('TEST_FILES_DIR', os.path.dirname(os.path.dirname(__file__)))

# 测试文件
RS_FILE = os.path.join(TEST_FILES_DIR, 'RS 样例.docx')
TS_FILE = os.path.join(TEST_FILES_DIR, 'TS 样例.docx')
MAPPING_FILE = os.path.join(TEST_FILES_DIR, 'mapping 样例.xlsx')
TEMPLATE_FILE = os.path.join(TEST_FILES_DIR, '测试设计模板.xmind')


def test_health():
    """测试 1: 健康检查"""
    print("\n" + "="*60)
    print("测试 1: 健康检查")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/health", timeout=5)
        data = response.json()
        
        if data['status'] == 'ok':
            print(f"[✓] 健康检查通过")
            print(f"    版本：{data['version']}")
            print(f"    时间：{data['timestamp']}")
            return True
        else:
            print(f"[✗] 健康检查失败：{data}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"[✗] 无法连接到 API 服务：{API_BASE_URL}")
        print(f"    请确保服务已启动：python api/run.py")
        return False
    except Exception as e:
        print(f"[✗] 测试失败：{e}")
        return False


def test_get_config():
    """测试 2: 获取配置"""
    print("\n" + "="*60)
    print("测试 2: 获取配置")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/config", timeout=5)
        data = response.json()
        
        print(f"[✓] 配置获取成功")
        print(f"    LLM 提供商：{data.get('llm_provider')}")
        print(f"    LLM 模型：{data.get('llm_model')}")
        print(f"    最大输入 Token: {data.get('max_input_tokens')}")
        print(f"    生成策略：{data.get('strategy')}")
        return True
        
    except Exception as e:
        print(f"[✗] 测试失败：{e}")
        return False


def test_generate_design():
    """测试 3: 生成测试设计"""
    print("\n" + "="*60)
    print("测试 3: 生成测试设计")
    print("="*60)
    
    # 检查测试文件是否存在
    missing_files = []
    for file_path, name in [(RS_FILE, 'RS'), (TS_FILE, 'TS'), 
                            (MAPPING_FILE, 'Mapping'), (TEMPLATE_FILE, '模板')]:
        if not os.path.exists(file_path):
            missing_files.append(f"{name}: {file_path}")
    
    if missing_files:
        print(f"[!] 跳过测试，缺少文件:")
        for f in missing_files:
            print(f"    - {f}")
        return False
    
    try:
        # 准备文件
        files = {
            'rs': ('RS 样例.docx', open(RS_FILE, 'rb'), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            'ts': ('TS 样例.docx', open(TS_FILE, 'rb'), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            'mapping': ('mapping 样例.xlsx', open(MAPPING_FILE, 'rb'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            'template': ('测试设计模板.xmind', open(TEMPLATE_FILE, 'rb'), 'application/vnd.xmind.worksheet')
        }
        
        data = {
            'strategy': 'auto'
        }
        
        print(f"[→] 发送请求...")
        start_time = time.time()
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/generate-design",
            files=files,
            data=data,
            timeout=300  # 5 分钟超时
        )
        
        duration = time.time() - start_time
        
        # 关闭文件
        for f in files.values():
            f[1].close()
        
        # 检查响应
        if response.status_code != 200:
            print(f"[✗] 请求失败，状态码：{response.status_code}")
            print(f"    响应：{response.text}")
            return False
        
        result = response.json()
        
        if not result.get('success'):
            print(f"[✗] 生成失败：{result.get('message')}")
            return False
        
        # 显示结果
        data = result.get('data', {})
        stats = data.get('stats', {})
        
        print(f"[✓] 测试设计生成成功")
        print(f"    耗时：{duration:.2f}s")
        print(f"    策略：{stats.get('strategy', 'N/A')}")
        print(f"    叶子节点数：{stats.get('leaf_nodes', 'N/A')}")
        print(f"    LLM 调用次数：{stats.get('llm_calls', 'N/A')}")
        print(f"    XMind 路径：{data.get('xmind_path', 'N/A')}")
        
        # 验证设计结构
        design = data.get('design', {})
        root = design.get('root', {})
        print(f"    根节点：{root.get('title', 'N/A')}")
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"[✗] 请求超时 (>5 分钟)")
        return False
    except Exception as e:
        print(f"[✗] 测试失败：{e}")
        return False


def test_download_xmind(xmind_path):
    """测试 4: 下载 XMind 文件"""
    print("\n" + "="*60)
    print("测试 4: 下载 XMind 文件")
    print("="*60)
    
    if not xmind_path:
        print(f"[!] 跳过测试，无 XMind 文件路径")
        return False
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/download-xmind",
            params={'path': xmind_path},
            timeout=30
        )
        
        if response.status_code == 200:
            output_path = os.path.join(TEST_FILES_DIR, 'output', 'test_design_from_api.xmind')
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"[✓] XMind 文件下载成功")
            print(f"    保存路径：{output_path}")
            return True
        else:
            print(f"[✗] 下载失败，状态码：{response.status_code}")
            return False
            
    except Exception as e:
        print(f"[✗] 测试失败：{e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("数仓测试用例生成 API - 测试套件")
    print("="*60)
    print(f"API 地址：{API_BASE_URL}")
    print(f"测试文件目录：{TEST_FILES_DIR}")
    
    results = []
    xmind_path = None
    
    # 测试 1: 健康检查
    if test_health():
        results.append(('健康检查', True))
    else:
        print("\n[!] 服务未运行，跳过后续测试")
        return results
    
    # 测试 2: 获取配置
    if test_get_config():
        results.append(('获取配置', True))
    else:
        results.append(('获取配置', False))
    
    # 测试 3: 生成测试设计
    if test_generate_design():
        results.append(('生成测试设计', True))
        # 获取 XMind 路径用于下载测试
        # 注意：实际需要从响应中提取，这里简化处理
    else:
        results.append(('生成测试设计', False))
    
    # 测试 4: 下载 XMind (如果有路径)
    # 实际使用时需要从测试 3 的响应中提取 xmind_path
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {name}")
    
    print(f"\n总计：{passed}/{total} 通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有测试通过!")
    else:
        print(f"\n[WARNING] {total - passed} 个测试失败")
    
    return results


if __name__ == '__main__':
    run_all_tests()
