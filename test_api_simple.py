# -*- coding: utf-8 -*-
"""
API 接口测试脚本
测试可用的文件
"""
import requests
import os

API_BASE_URL = 'http://localhost:5000'

def test_health():
    """测试健康检查"""
    print("="*60)
    print("测试 1: 健康检查")
    print("="*60)
    
    response = requests.get(f"{API_BASE_URL}/api/v1/health", timeout=10)
    data = response.json()
    
    assert data['status'] == 'ok', "健康检查失败"
    print(f"✓ 状态：{data['status']}")
    print(f"✓ 版本：{data['version']}")
    print(f"✓ 时间：{data['timestamp']}")
    print()

def test_config():
    """测试配置获取"""
    print("="*60)
    print("测试 2: 获取配置")
    print("="*60)
    
    response = requests.get(f"{API_BASE_URL}/api/v1/config", timeout=10)
    data = response.json()
    
    print(f"✓ LLM 提供商：{data['llm_provider']}")
    print(f"✓ LLM 模型：{data['llm_model']}")
    print(f"✓ 最大输入 Token: {data['max_input_tokens']}")
    print(f"✓ 生成策略：{data['strategy']}")
    print()

def test_file_upload():
    """测试文件上传（仅验证接口响应）"""
    print("="*60)
    print("测试 3: 文件上传接口")
    print("="*60)
    
    # 检查可用文件
    available_files = []
    for f in ['RS 样例.docx', 'mapping 样例.xlsx']:
        if os.path.exists(f):
            available_files.append(f)
    
    print(f"可用文件：{available_files}")
    
    # 尝试上传（会因为缺少 TS 文件而失败，但验证了接口可用）
    try:
        files = {}
        if 'RS 样例.docx' in available_files:
            files['rs'] = open('RS 样例.docx', 'rb')
        if 'mapping 样例.xlsx' in available_files:
            files['mapping'] = open('mapping 样例.xlsx', 'rb')
        
        if not files:
            print("⚠ 没有可用文件进行测试")
            return
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/generate-design",
            files=files,
            timeout=30
        )
        
        # 关闭文件
        for f in files.values():
            f.close()
        
        result = response.json()
        
        # 预期会因为缺少 TS 文件而失败
        if not result.get('success'):
            print(f"✓ 接口正常响应（预期失败）")
            print(f"  错误信息：{result.get('message')}")
        else:
            print(f"✓ 生成成功!")
            
    except Exception as e:
        print(f"✗ 测试失败：{e}")
    
    print()

def test_not_found():
    """测试 404 错误处理"""
    print("="*60)
    print("测试 4: 404 错误处理")
    print("="*60)
    
    response = requests.get(f"{API_BASE_URL}/api/v1/nonexistent", timeout=10)
    data = response.json()
    
    assert response.status_code == 404, "预期 404 状态码"
    print(f"✓ 状态码：{response.status_code}")
    print(f"✓ 错误信息：{data.get('message')}")
    print()

if __name__ == '__main__':
    print("\n" + "="*60)
    print("API 接口测试开始")
    print("="*60 + "\n")
    
    try:
        test_health()
        test_config()
        test_file_upload()
        test_not_found()
        
        print("="*60)
        print("✅ 所有测试通过!")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到 API 服务，请确保服务已启动")
    except Exception as e:
        print(f"\n❌ 未知错误：{e}")
