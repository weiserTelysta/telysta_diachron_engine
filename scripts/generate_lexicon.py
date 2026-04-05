import sys
from pathlib import Path

# 确保能找到 app 目录（如果没装成包的话）
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.domain.lexicon.generate_raw_data import LexisGenerator
from app.core.config import configs

def main():
    print(f"--- 正在初始化时代 0 (Seed: {configs.SEED}) ---")
    
    # 1. 初始化生成器
    generator = LexisGenerator()
    
    # 2. 获取路径（从 config 获取）
    input_path = configs.get_lexicon_path()
    
    # 3. 执行生成
    entities = generator.from_swadesh_json(input_path)
    
    # 4. 保存快照（这部分后续可以封装进 repository 层）
    output_path = configs.SNAPSHOT_DIR / "era_0.json"
    # 这里可以添加保存逻辑...
    
    print(f"成功！已在 {output_path} 生成 {len(entities)} 个核心词汇。")

if __name__ == "__main__":
    main()