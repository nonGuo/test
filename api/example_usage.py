# -*- coding: utf-8 -*-
"""
API 调用示例脚本

展示如何使用 Python 调用测试设计生成 API
"""
import requests
import json
import os

# API 配置
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5000')


class TestCaseGeneratorClient:
    """测试用例生成 API 客户端"""
    
    def __init__(self, base_url=API_BASE_URL, timeout=300):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        
        # 配置重试策略
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def health_check(self):
        """健康检查"""
        response = self.session.get(
            f"{self.base_url}/api/v1/health",
            timeout=10
        )
        return response.json()
    
    def get_config(self):
        """获取配置信息"""
        response = self.session.get(
            f"{self.base_url}/api/v1/config",
            timeout=10
        )
        return response.json()
    
    def generate_design(self, rs_path, ts_path, mapping_path, 
                       template_path=None, strategy='auto'):
        """
        生成测试设计
        
        Args:
            rs_path: RS 文档路径
            ts_path: TS 文档路径
            mapping_path: Mapping 文档路径
            template_path: XMind 模板路径 (可选)
            strategy: 生成策略 (auto/full/by_branch/by_leaf)
        
        Returns:
            dict: 生成结果
        """
        # 准备文件
        files = {}
        
        with open(rs_path, 'rb') as f:
            files['rs'] = ('RS.docx', f)
            with open(ts_path, 'rb') as f2:
                files['ts'] = ('TS.docx', f2)
                with open(mapping_path, 'rb') as f3:
                    files['mapping'] = ('Mapping.xlsx', f3)
                    
                    if template_path:
                        with open(template_path, 'rb') as f4:
                            files['template'] = ('Template.xmind', f4)
                            response = self._send_request(files, strategy)
                    else:
                        response = self._send_request(files, strategy)
        
        return response
    
    def _send_request(self, files, strategy):
        """发送生成请求"""
        data = {'strategy': strategy}
        
        response = self.session.post(
            f"{self.base_url}/api/v1/generate-design",
            files=files,
            data=data,
            timeout=self.timeout
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                'success': False,
                'message': f'HTTP {response.status_code}: {response.text}'
            }
    
    def download_xmind(self, xmind_path, output_path):
        """
        下载 XMind 文件
        
        Args:
            xmind_path: 服务器上的 XMind 文件路径
            output_path: 本地保存路径
        """
        response = self.session.get(
            f"{self.base_url}/api/v1/download-xmind",
            params={'path': xmind_path},
            timeout=30
        )
        
        if response.status_code == 200:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
        return False


# ==================== 使用示例 ====================

def example_basic_usage():
    """基础使用示例"""
    print("="*60)
    print("基础使用示例")
    print("="*60)
    
    client = TestCaseGeneratorClient()
    
    # 1. 健康检查
    health = client.health_check()
    print(f"服务状态：{health['status']}")
    print(f"版本：{health['version']}")
    
    # 2. 生成测试设计
    result = client.generate_design(
        rs_path='RS 样例.docx',
        ts_path='TS 样例.docx',
        mapping_path='mapping 样例.xlsx',
        template_path='测试设计模板.xmind',
        strategy='auto'
    )
    
    if result['success']:
        print("\n✓ 生成成功!")
        stats = result['data']['stats']
        print(f"  策略：{stats['strategy']}")
        print(f"  叶子节点数：{stats['leaf_nodes']}")
        print(f"  耗时：{stats['duration_seconds']}s")
        print(f"  LLM 调用次数：{stats['llm_calls']}")
        
        # 3. 下载 XMind 文件
        xmind_path = result['data']['xmind_path']
        output_path = 'output/test_design.xmind'
        
        if client.download_xmind(xmind_path, output_path):
            print(f"\n✓ XMind 文件已保存：{output_path}")
    else:
        print(f"\n✗ 生成失败：{result['message']}")


def example_with_error_handling():
    """带错误处理的示例"""
    print("\n" + "="*60)
    print("错误处理示例")
    print("="*60)
    
    client = TestCaseGeneratorClient(timeout=60)
    
    try:
        # 检查服务是否可用
        health = client.health_check()
        
        # 检查 API Key 配置
        config = client.get_config()
        if not config.get('llm_provider'):
            print("[错误] 未配置 LLM 提供商")
            return
        
        # 生成测试设计
        result = client.generate_design(
            rs_path='RS 样例.docx',
            ts_path='TS 样例.docx',
            mapping_path='mapping 样例.xlsx',
            strategy='by_branch'  # 强制使用按分支生成
        )
        
        if not result['success']:
            print(f"[错误] {result['message']}")
            return
        
        # 处理结果
        design = result['data']['design']
        print(f"根节点：{design['root']['title']}")
        print(f"目标表：{design.get('target_table', 'N/A')}")
        
    except FileNotFoundError as e:
        print(f"[错误] 文件不存在：{e}")
    except requests.exceptions.Timeout:
        print("[错误] 请求超时，请增加 timeout 值")
    except requests.exceptions.ConnectionError:
        print("[错误] 无法连接到 API 服务")
    except Exception as e:
        print(f"[错误] 未知错误：{e}")


def example_batch_generation():
    """批量生成示例"""
    print("\n" + "="*60)
    print("批量生成示例")
    print("="*60)
    
    client = TestCaseGeneratorClient()
    
    # 多个项目的测试设计生成
    projects = [
        {'name': 'project_a', 'rs': 'project_a/RS.docx', 'ts': 'project_a/TS.docx', 'mapping': 'project_a/Mapping.xlsx'},
        {'name': 'project_b', 'rs': 'project_b/RS.docx', 'ts': 'project_b/TS.docx', 'mapping': 'project_b/Mapping.xlsx'},
    ]
    
    for project in projects:
        print(f"\n处理项目：{project['name']}")
        
        try:
            result = client.generate_design(
                rs_path=project['rs'],
                ts_path=project['ts'],
                mapping_path=project['mapping'],
                strategy='auto'
            )
            
            if result['success']:
                stats = result['data']['stats']
                print(f"  ✓ 完成 - 叶子节点：{stats['leaf_nodes']}, 耗时：{stats['duration_seconds']}s")
            else:
                print(f"  ✗ 失败 - {result['message']}")
                
        except Exception as e:
            print(f"  ✗ 异常 - {e}")


if __name__ == '__main__':
    # 运行示例
    example_basic_usage()
    example_with_error_handling()
    # example_batch_generation()  # 取消注释以运行批量生成示例
