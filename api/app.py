# -*- coding: utf-8 -*-
"""
数仓测试用例生成工具 - Flask API 服务
提供长上下文处理的 HTTP 接口
"""
import os
import json
import logging
import tempfile
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

# 导入核心模块
from core.ai import LLMClientFactory
from core.parser.document_parser import RSParser, TSParser
from core.parser.mapping_parser import MappingParser
from core.analyzer import DesignGenerator
from core.generator import XMindGenerator
from core.models import TestDesign

# ==================== 配置管理 ====================

class Config:
    """API 配置类"""
    
    # 基础配置
    DEBUG = os.getenv('API_DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('API_HOST', '0.0.0.0')
    PORT = int(os.getenv('API_PORT', '5000'))
    
    # 文件上传配置
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', tempfile.gettempdir())
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    ALLOWED_EXTENSIONS = {'docx', 'xlsx', 'xmind', 'pdf'}
    
    # AI 配置
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'qwen')
    LLM_MODEL = os.getenv('LLM_MODEL', 'qwen-max')
    LLM_API_KEY = os.getenv('QWEN_API_KEY') or os.getenv('OPENAI_API_KEY')
    
    # 生成器配置
    MAX_INPUT_TOKENS = int(os.getenv('MAX_INPUT_TOKENS', '8000'))
    GENERATION_STRATEGY = os.getenv('GENERATION_STRATEGY', 'auto')
    
    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 版本信息
    VERSION = '1.0.0'


# ==================== Flask 应用 ====================

def create_app(config_class=Config):
    """创建 Flask 应用"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 配置
    app.config['UPLOAD_FOLDER'] = config_class.UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = config_class.MAX_CONTENT_LENGTH
    
    # 初始化日志
    setup_logging(app)
    
    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # 注册路由
    register_routes(app)
    
    # 注册错误处理
    register_error_handlers(app)
    
    logger = logging.getLogger(__name__)
    logger.info(f"API 服务启动成功 - 版本：{config_class.VERSION}")
    
    return app


def setup_logging(app):
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, app.config['LOG_LEVEL']),
        format=app.config['LOG_FORMAT']
    )
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))


# ==================== 路由定义 ====================

def register_routes(app):
    """注册路由"""
    
    @app.route('/api/v1/health', methods=['GET'])
    def health_check():
        """健康检查接口"""
        return jsonify({
            'status': 'ok',
            'version': Config.VERSION,
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/generate-design', methods=['POST'])
    def generate_design():
        """
        生成测试设计接口
        
        请求：multipart/form-data
        - rs: RS 文档文件 (必需)
        - ts: TS 文档文件 (必需)
        - mapping: Mapping 文档文件 (必需)
        - template: XMind 模板文件 (可选，默认使用内置模板)
        - strategy: 生成策略 (可选，默认 auto)
        
        响应：
        {
            "success": true,
            "data": {
                "design": {...},  # 测试设计 JSON
                "xmind_path": "...",  # XMind 文件路径 (如果指定 output)
                "stats": {
                    "strategy": "by_branch",
                    "llm_calls": 3,
                    "leaf_nodes": 10,
                    "duration_seconds": 15.5
                }
            },
            "message": "生成成功"
        }
        """
        logger = logging.getLogger(__name__)
        start_time = datetime.now()
        
        try:
            # 验证必需文件
            if 'rs' not in request.files or 'ts' not in request.files or 'mapping' not in request.files:
                return jsonify({
                    'success': False,
                    'message': '缺少必需文件：rs, ts, mapping'
                }), 400
            
            rs_file = request.files['rs']
            ts_file = request.files['ts']
            mapping_file = request.files['mapping']
            template_file = request.files.get('template')
            strategy = request.form.get('strategy', Config.GENERATION_STRATEGY)
            
            # 验证文件扩展名
            if not _allowed_file(rs_file.filename, ['docx', 'pdf']):
                return jsonify({'success': False, 'message': 'RS 文件格式不支持'}), 400
            if not _allowed_file(ts_file.filename, ['docx', 'pdf']):
                return jsonify({'success': False, 'message': 'TS 文件格式不支持'}), 400
            if not _allowed_file(mapping_file.filename, ['xlsx', 'csv']):
                return jsonify({'success': False, 'message': 'Mapping 文件格式不支持'}), 400
            
            # 保存临时文件
            temp_dir = tempfile.mkdtemp(dir=app.config['UPLOAD_FOLDER'])
            rs_path = _save_uploaded_file(rs_file, temp_dir)
            ts_path = _save_uploaded_file(ts_file, temp_dir)
            mapping_path = _save_uploaded_file(mapping_file, temp_dir)
            template_path = None
            
            if template_file:
                template_path = _save_uploaded_file(template_file, temp_dir)
            else:
                # 使用默认模板
                default_template = os.path.join(os.path.dirname(__file__), '..', '测试设计模板.xmind')
                if os.path.exists(default_template):
                    template_path = default_template
            
            if not template_path:
                return jsonify({
                    'success': False,
                    'message': '未提供 XMind 模板文件'
                }), 400
            
            logger.info(f"开始生成测试设计 - 策略：{strategy}")
            logger.info(f"RS: {rs_path}, TS: {ts_path}, Mapping: {mapping_path}")
            
            # 初始化 LLM 客户端
            if not Config.LLM_API_KEY:
                return jsonify({
                    'success': False,
                    'message': '未配置 LLM API Key，请设置 QWEN_API_KEY 或 OPENAI_API_KEY 环境变量'
                }), 500
            
            llm_client = LLMClientFactory.create(
                provider=Config.LLM_PROVIDER,
                model=Config.LLM_MODEL
            )
            
            # 解析文档
            logger.info("解析 RS 文档...")
            rs_parser = RSParser()
            rs_result = rs_parser.parse(rs_path)
            rs_content = rs_parser.to_prompt_content(rs_result)
            
            logger.info("解析 TS 文档...")
            ts_parser = TSParser()
            ts_result = ts_parser.parse(ts_path, llm_client=llm_client)
            ts_content = ts_parser.to_prompt_content(ts_result)
            
            logger.info("解析 Mapping 文档...")
            mapping_parser = MappingParser()
            mapping_result = mapping_parser.parse(mapping_path)
            mapping_content = str(mapping_result)
            
            # 生成测试设计
            logger.info(f"生成测试设计 (策略：{strategy})...")
            design_generator = DesignGenerator(
                llm_client=llm_client,
                template_path=template_path,
                strategy=strategy,
                max_input_tokens=Config.MAX_INPUT_TOKENS
            )
            
            design = design_generator.generate(rs_content, ts_content, mapping_content)
            
            # 生成 XMind 文件
            output_xmind_path = os.path.join(temp_dir, 'test_design.xmind')
            xmind_gen = XMindGenerator(template_path=template_path)
            xmind_gen.generate(design, output_xmind_path)
            
            # 计算统计信息
            duration = (datetime.now() - start_time).total_seconds()
            stats = {
                'strategy': strategy,
                'leaf_nodes': len(design.get_all_leaf_nodes()),
                'duration_seconds': round(duration, 2),
                'llm_calls': getattr(design_generator, 'llm_call_count', 0)
            }
            
            # 返回结果
            design_dict = _design_to_dict(design)
            
            response = {
                'success': True,
                'data': {
                    'design': design_dict,
                    'xmind_path': output_xmind_path,
                    'stats': stats
                },
                'message': '测试设计生成成功'
            }
            
            logger.info(f"测试设计生成完成 - 耗时：{duration:.2f}s, 叶子节点数：{stats['leaf_nodes']}")
            
            return jsonify(response)
            
        except Exception as e:
            logger.exception(f"生成测试设计失败：{e}")
            return jsonify({
                'success': False,
                'message': f'生成失败：{str(e)}'
            }), 500
    
    @app.route('/api/v1/generate-design-async', methods=['POST'])
    def generate_design_async():
        """
        异步生成测试设计接口
        
        适用于大型项目，避免请求超时
        
        请求：同 /generate-design
        响应：
        {
            "success": true,
            "task_id": "xxx",
            "message": "任务已提交，请使用 task_id 查询进度"
        }
        """
        # TODO: 实现异步任务队列（可使用 Celery 或 RQ）
        return jsonify({
            'success': False,
            'message': '异步接口暂未实现，请使用同步接口'
        }), 501
    
    @app.route('/api/v1/task/<task_id>', methods=['GET'])
    def get_task_status(task_id):
        """
        查询异步任务状态
        
        响应：
        {
            "task_id": "xxx",
            "status": "pending|running|completed|failed",
            "progress": 50,
            "result": {...}  # 完成后返回
        }
        """
        # TODO: 实现异步任务状态查询
        return jsonify({
            'task_id': task_id,
            'status': 'not_implemented',
            'message': '异步任务接口暂未实现'
        }), 501
    
    @app.route('/api/v1/download-xmind', methods=['GET'])
    def download_xmind():
        """
        下载 XMind 文件
        
        请求参数：
        - path: XMind 文件路径
        
        响应：XMind 文件
        """
        file_path = request.args.get('path')
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': '文件不存在'
            }), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name='test_design.xmind',
            mimetype='application/vnd.xmind.worksheet'
        )
    
    @app.route('/api/v1/config', methods=['GET'])
    def get_config():
        """获取当前配置信息（不包含敏感信息）"""
        return jsonify({
            'version': Config.VERSION,
            'llm_provider': Config.LLM_PROVIDER,
            'llm_model': Config.LLM_MODEL,
            'max_input_tokens': Config.MAX_INPUT_TOKENS,
            'strategy': Config.GENERATION_STRATEGY,
            'upload_folder': Config.UPLOAD_FOLDER,
            'max_content_length': Config.MAX_CONTENT_LENGTH
        })


def register_error_handlers(app):
    """注册错误处理器"""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'message': '请求参数错误'
        }), 400
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({
            'success': False,
            'message': f'文件过大，最大允许 {Config.MAX_CONTENT_LENGTH // 1024 // 1024}MB'
        }), 413
    
    @app.errorhandler(500)
    def internal_server_error(error):
        logging.exception('内部错误')
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'message': '接口不存在'
        }), 404


# ==================== 辅助函数 ====================

def _allowed_file(filename, allowed_extensions):
    """检查文件扩展名是否允许"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions


def _save_uploaded_file(file_obj, save_dir):
    """保存上传的文件"""
    filename = secure_filename(file_obj.filename)
    # 添加时间戳避免重名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(filename)
    new_filename = f"{name}_{timestamp}{ext}"
    file_path = os.path.join(save_dir, new_filename)
    file_obj.save(file_path)
    return file_path


def _design_to_dict(design):
    """将 TestDesign 对象转换为字典"""
    def node_to_dict(node):
        result = {
            'title': node.title,
            'description': getattr(node, 'description', None),
            'priority': getattr(node, 'priority', None),
            'tables': getattr(node, 'tables', [])
        }
        children = getattr(node, 'children', [])
        if children:
            result['children'] = [node_to_dict(c) for c in children]
        return result
    
    return {
        'root': node_to_dict(design.root),
        'source_tables': getattr(design, 'source_tables', []),
        'target_table': getattr(design, 'target_table', None),
        'mapping_rules': getattr(design, 'mapping_rules', [])
    }


# ==================== 应用入口 ====================

if __name__ == '__main__':
    app = create_app()
    print(f"""
╔══════════════════════════════════════════════════════════╗
║   数仓测试用例生成工具 - API 服务                          ║
╠══════════════════════════════════════════════════════════╣
║   版本：{Config.VERSION}
║   地址：http://{Config.HOST}:{Config.PORT}
║   文档：http://{Config.HOST}:{Config.PORT}/api/docs
╚══════════════════════════════════════════════════════════╝
    """)
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
