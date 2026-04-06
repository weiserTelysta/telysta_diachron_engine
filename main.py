# main.py
from app.core.settings import global_settings
from app.domain.lexicon.factory import create_basic_lexicon_generator


def bootstrap_app():
    """
    启动前的统筹工作：接收外部输入，更新全局设置。
    """
    # 假设这是从命令行或 UI 前端接收到的 JSON 数据
    ui_mock_data = {"seed": 888, "is_llm": False}

    # 更新系统配置
    global_settings.modify_settings(ui_mock_data)
    print("[Main] 系统引导完成，配置已就绪。")


def main():
    # 1. 引导程序启动
    bootstrap_app()

    # 2. 呼叫工厂，制造一个引擎实例
    # 注意：main 根本不知道引擎是用什么辅音造词的，实现了完美解耦！
    engine = create_basic_lexicon_generator(global_settings)

    # 3. 按下启动按钮
    generated_words = engine.generate()

    # 4. 善后工作
    print(f"\n[Main] 任务结束。共生成 {len(generated_words)} 个核心词汇。")
    # 以后保存到文件的逻辑，也可以放在这里调用


if __name__ == "__main__":
    main()
