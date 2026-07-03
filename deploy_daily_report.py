#!/usr/bin/env python3
"""
===================================================
  AI日报工作流 — 一键部署脚本
  中科汇航 · 王玉川
===================================================

使用方法：
  1. 把这个文件交给你的AI助手（Codex/Hermes/Claude Code等）
  2. 说一句："帮我运行这个脚本部署AI日报"
  3. 跟着提示操作即可

说明：
  - 本脚本会自动创建GitHub仓库，部署日报推送代码
  - 每天8:05自动采集行业动态推送到你的钉钉群
  - 全程零成本，跑在GitHub免费服务器上
  
需要你先准备：
  ✅ GitHub账号（免费注册：github.com）
  ✅ 能在钉钉建群（2分钟）
"""

import subprocess, sys, json, os, time, uuid, base64, stat, textwrap, shutil
from pathlib import Path

# ===========================================================
# 配置 - 如果你要修改，只改这里
# ===========================================================
TEMPLATE_REPO = "yuchuanwang001-source/canyin-ai-news"  # 我们的模板仓库
BRANCH = "main"

# ===========================================================
# 工具函数
# ===========================================================

def print_banner():
    print("=" * 60)
    print("  📡 AI日报工作流 · 一键部署")
    print("  中科汇航 · 王玉川")
    print("=" * 60)
    print()

def print_step(step, text):
    print(f"\n  [{step}] {text}")
    print("-" * 50)

def print_info(text):
    print(f"     💡 {text}")

def print_ok(text):
    print(f"     ✅ {text}")

def print_warn(text):
    print(f"     ⚠️  {text}")

def print_input(text):
    print(f"     ▶ {text}")

def run_cmd(cmd, timeout=60, check=True):
    """运行命令并返回输出（兼容Windows GBK编码）"""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        # 先尝试utf-8解码，失败则用gbk忽略错误
        try:
            stdout = r.stdout.decode('utf-8').strip()
        except:
            stdout = r.stdout.decode('gbk', errors='replace').strip()
        try:
            stderr = r.stderr.decode('utf-8').strip()
        except:
            stderr = r.stderr.decode('gbk', errors='replace').strip()
        if check and r.returncode != 0:
            return False, stderr or stdout
        return True, stdout
    except subprocess.TimeoutExpired:
        return False, "命令超时"
    except FileNotFoundError:
        return False, "找不到命令，请检查是否已安装"

def ask(question, default=None):
    """问用户一个问题"""
    if default:
        print_input(f"{question} (回车用默认值: {default})")
    else:
        print_input(question)
    try:
        val = input("     > ").strip()
        if not val and default:
            return default
        return val
    except (EOFError, KeyboardInterrupt):
        print()
        return default or ""

# ===========================================================
# 主流程
# ===========================================================

def main():
    print_banner()

    # ---- 第1步：检查环境 ----
    print_step("1/6", "检查你的环境")
    
    # 检查gh CLI
    ok, gh_version = run_cmd("gh --version", check=False)
    has_gh = ok
    if has_gh:
        print_ok(f"已安装 GitHub CLI: {gh_version.split(chr(10))[0]}")
    else:
        print_warn("未检测到 GitHub CLI (gh)")

    # 检查Python
    ok, py_version = run_cmd("python3 --version 2>&1 || python --version 2>&1", check=False)
    if ok:
        print_ok(f"已安装 Python: {py_version}")
        PYTHON = "python3" if "python3" in py_version.lower() else "python"
    else:
        print_warn("未检测到 Python")
        print_info("脚本自身就是Python，能跑说明Python已安装")
        PYTHON = "python3"

    # 检查git
    ok, _ = run_cmd("git --version", check=False)
    has_git = ok
    if has_git:
        print_ok("已安装 Git")
    else:
        print_warn("未检测到 Git")

    # ---- 第2步：GitHub登录 ----
    print_step("2/6", "登录GitHub账号")

    print_info("需要GitHub账号才能创建仓库")
    print_info("如果没有，现在去 github.com 注册一个（免费）")
    print()

    github_token = ""

    if has_gh:
        # 尝试用gh
        ok, whoami = run_cmd("gh auth status 2>&1", check=False)
        if ok and "Logged in" in whoami:
            print_ok(f"gh 已登录")
            ok, token = run_cmd("gh auth token", check=False)
            if ok and token:
                github_token = token
                print_ok("已获取到GitHub Token")
        else:
            print_warn("gh 未登录")
            print_input("请输入 GitHub Token")
            print()
            print_info("获取Token的方法：")
            print_info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print_info("1. 打开浏览器，访问：")
            print_info("   https://github.com/settings/tokens/new")
            print_info("")
            print_info("2. 页面上的设置：")
            print_info("   • Note（备注）：填「AI日报部署」")
            print_info("   • Expiration（过期）：选「No expiration」")
            print_info("   • 下面勾选权限：只勾「repo」（全部勾上）和「workflow」")
            print_info("")
            print_info("3. 点页面底部的绿色按钮「Generate token」")
            print_info("")
            print_info("4. 会生成一串以 ghp_ 开头的字符，复制它")
            print_info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print()
            github_token = input("     > 粘贴到此处按回车: ").strip()
            if not github_token:
                print_warn("未输入Token，尝试用 gh auth login 登录")
                run_cmd("gh auth login", timeout=120, check=False)
                ok, token = run_cmd("gh auth token", check=False)
                if ok and token:
                    github_token = token
                    print_ok("登录成功")
    else:
        print_input("请输入 GitHub Token")
        print()
        print_info("获取Token的方法：")
        print_info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print_info("1. 打开浏览器，访问：")
        print_info("   https://github.com/settings/tokens/new")
        print_info("")
        print_info("2. 页面上的设置：")
        print_info("   • Note（备注）：填「AI日报部署」")
        print_info("   • Expiration（过期）：选「No expiration」")
        print_info("   • 下面勾选权限：只勾「repo」（全部勾上）和「workflow」")
        print_info("")
        print_info("3. 点页面底部的绿色按钮「Generate token」")
        print_info("")
        print_info("4. 会生成一串以 ghp_ 开头的字符，复制它")
        print_info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        github_token = input("     > 粘贴到此处按回车: ").strip()
        while not github_token:
            print_warn("Token不能为空，请重新输入")
            github_token = input("     > ").strip()

    # 验证Token
    print_info("验证Token...")
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json"
    }
    
    import urllib.request
    try:
        req = urllib.request.Request("https://api.github.com/user", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            user_info = json.loads(r.read().decode())
            username = user_info["login"]
            print_ok(f"Token验证成功！GitHub用户: {username}")
    except Exception as e:
        print_warn(f"Token验证失败: {e}")
        print_info("请检查Token是否正确，以及权限是否勾选")
        retry = ask("重新输入Token？(y/n)", "y")
        if retry.lower() == "y":
            github_token = input("     > ").strip()
            # 重新验证
            headers["Authorization"] = f"token {github_token}"
            try:
                req = urllib.request.Request("https://api.github.com/user", headers=headers)
                with urllib.request.urlopen(req, timeout=15) as r:
                    user_info = json.loads(r.read().decode())
                    username = user_info["login"]
                    print_ok(f"Token验证成功！GitHub用户: {username}")
            except:
                print_warn("仍然失败，退出部署")
                sys.exit(1)
        else:
            print_warn("退出部署")
            sys.exit(1)

    # ---- 第3步：获取钉钉Token ----
    print_step("3/6", "配置钉钉机器人")
    
    print_info("现在需要你去钉钉建一个群，并添加机器人拿到Token")
    print()
    print_info("操作步骤：")
    print_info("1. 打开钉钉 → 右上角'+' → 发起群聊 → 建一个群")
    print_info("2. 群设置 → 智能群助手 → 添加机器人 → 选择'自定义'")
    print_info("3. 机器人名字填：AI日报助手")
    print_info("4. 创建完成后，复制 Webhook 地址")
    print_info("5. 地址格式类似：")
    print_info("   https://oapi.dingtalk.com/robot/send?access_token=xxx")
    print_info("   你只需要复制 xxx 这部分（access_token=后面的字符串）")
    print()
    
    dingtalk_token = ask("请输入钉钉机器人的Token")
    while not dingtalk_token:
        print_warn("Token不能为空")
        dingtalk_token = ask("请输入钉钉机器人的Token")
    
    print_ok("Token已获取")

    # ---- 第4步：创建仓库（通过Fork模板仓库） ----
    print_step("4/6", "创建GitHub仓库并部署代码")
    
    repo_name = f"canyin-ai-news-{username}"
    print_info(f"将Fork模板仓库到: {username}/{repo_name}")
    print_info("正在Fork（这比逐文件复制更可靠，不会漏掉任何文件）...")
    
    fork_data = json.dumps({
        "name": repo_name,
        "organization": None
    }).encode()
    
    try:
        # Fork模板仓库
        req = urllib.request.Request(
            f"https://api.github.com/repos/{TEMPLATE_REPO}/forks",
            data=fork_data,
            headers={**headers, "Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read().decode())
            print_ok(f"Fork成功！仓库: {result['full_name']}")
            print_info("等待GitHub完成复制...")
            time.sleep(5)  # 等待fork完成
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if e.code == 422 and "already" in error_body:
            print_warn(f"仓库 {repo_name} 已存在（可能是之前部署过）")
            overwrite = ask("要删除重建吗？(y/n)", "n")
            if overwrite.lower() == "y":
                # 先删除
                print_info("正在删除旧仓库...")
                try:
                    del_req = urllib.request.Request(
                        f"https://api.github.com/repos/{username}/{repo_name}",
                        headers=headers,
                        method="DELETE"
                    )
                    with urllib.request.urlopen(del_req, timeout=30) as dr:
                        pass
                    print_ok("旧仓库已删除，重新Fork中...")
                    time.sleep(3)
                    req = urllib.request.Request(
                        f"https://api.github.com/repos/{TEMPLATE_REPO}/forks",
                        data=fork_data,
                        headers={**headers, "Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=60) as r:
                        result = json.loads(r.read().decode())
                        print_ok(f"Fork成功！仓库: {result['full_name']}")
                        time.sleep(5)
                except Exception as del_err:
                    print_warn(f"删除失败: {del_err}")
                    print_info("请手动去GitHub删除这个仓库，然后重试")
                    sys.exit(1)
            else:
                print_info("使用已有仓库继续...")
                # 检查仓库是否存在且有代码
                try:
                    check_req = urllib.request.Request(
                        f"https://api.github.com/repos/{username}/{repo_name}/git/trees/main?recursive=1",
                        headers=headers
                    )
                    with urllib.request.urlopen(check_req, timeout=15) as cr:
                        check_data = json.loads(cr.read().decode())
                        file_count = len([i for i in check_data.get("tree", []) if i["type"] == "blob"])
                        if file_count < 5:
                            print_warn(f"仓库文件不全（仅{file_count}个），建议删除重建")
                            sys.exit(1)
                        print_ok(f"仓库已有代码（{file_count}个文件）")
                except:
                    print_warn("仓库似乎没有main分支，请删除后重试")
                    sys.exit(1)
        else:
            print_warn(f"Fork失败: {e}")
            print_info(f"错误详情: {error_body}")
            print_info("请检查Token权限（需要repo和workflow权限）")
            sys.exit(1)

    # ---- 第5步：设置Secrets + 开启Actions ----
    print_step("5/6", "配置自动推送")

    # 设置DINGTALK_TOKEN到Secrets
    print_info("正在设置钉钉Token到仓库Secrets...")
    
    try:
        # 先获取公钥
        req = urllib.request.Request(
            f"https://api.github.com/repos/{username}/{repo_name}/actions/secrets/public-key",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            key_data = json.loads(r.read().decode())
            public_key = key_data["key"]
            key_id = key_data["key_id"]
        
        # 用公钥加密Token（GitHub API用libsodium）
        # 简单做法：直接用GitHub API的加密要求
        # 实际上需要用nacl库加密，但我们用简单方式
        
        # 用gh CLI来设置（如果有），否则用API
        if has_gh:
            ok, _ = run_cmd(
                f'gh secret set DINGTALK_TOKEN --repo "{username}/{repo_name}" --body "{dingtalk_token}"',
                timeout=15,
                check=False
            )
            if ok:
                print_ok("钉钉Token已设置到仓库Secrets")
            else:
                print_warn("gh设置Secrets失败，改用API方式")
        
        # 如果gh方式失败或没有gh，用API创建secret
        # 注意：GitHub API创建secret需要libsodium加密，这里简化处理
        # 如果gh没有设置成功，提示用户手动设置
        print_info("验证Secrets是否设置成功...")
        req = urllib.request.Request(
            f"https://api.github.com/repos/{username}/{repo_name}/actions/secrets",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            secrets_data = json.loads(r.read().decode())
            secret_names = [s["name"] for s in secrets_data.get("secrets", [])]
            if "DINGTALK_TOKEN" in secret_names:
                print_ok("DINGTALK_TOKEN 已设置")
            else:
                print_warn("未能自动设置Secrets")
                print_info("请手动设置：")
                print_info(f"  1. 打开 https://github.com/{username}/{repo_name}/settings/secrets/actions")
                print_info(f"  2. 点 'New repository secret'")
                print_info(f"  3. Name: DINGTALK_TOKEN")
                print_info(f"  4. Secret: {dingtalk_token[:8]}...（你刚才输入的Token）")
                print_info(f"  5. 点 'Add secret'")
                ask("设置完成后，按回车继续")
                
    except Exception as e:
        print_warn(f"设置Secrets时出错: {e}")
        print_info("请手动设置Secrets（见上方说明）")
        ask("设置完成后，按回车继续")

    # 启用Actions工作流
    print_info("正在启用GitHub Actions...")
    
    try:
        # 检查workflow是否存在
        req = urllib.request.Request(
            f"https://api.github.com/repos/{username}/{repo_name}/actions/workflows",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            workflows = json.loads(r.read().decode())
        
        workflow_id = None
        for wf in workflows.get("workflows", []):
            if "钉钉日报" in wf.get("name", "") or "dingtalk" in wf.get("path", ""):
                workflow_id = wf["id"]
                if wf["state"] == "active":
                    print_ok("工作流已启用")
                else:
                    # 启用
                    req = urllib.request.Request(
                        f"https://api.github.com/repos/{username}/{repo_name}/actions/workflows/{wf['id']}/enable",
                        headers=headers,
                        method="PUT"
                    )
                    with urllib.request.urlopen(req, timeout=15) as r:
                        print_ok("工作流已启用")
                break
        
        if not workflow_id:
            print_warn("未找到工作流文件，可能Fork还没完成")
            print_info("请稍后手动操作：")
            print_info(f"  1. 打开 https://github.com/{username}/{repo_name}/actions")
            print_info(f"  2. 如果有 'I understand my workflows, go ahead and enable them' 按钮，点它")
            print_info(f"  3. 点 'Run workflow' 手动触发一次测试")
            print_info("")
            print_info("或者等2分钟后刷新页面，Actions会自动出现")
            
    except Exception as e:
        print_warn(f"启用工作流时出错: {e}")
        print_info("请手动检查 Actions 是否已开启")

    # ---- 第6步：完成 ----
    print_step("6/6", "✅ 部署完成！")
    
    print()
    print("=" * 60)
    print("  🎉 AI日报工作流部署成功！")
    print("=" * 60)
    print()
    print(f"  仓库地址：")
    print(f"    https://github.com/{username}/{repo_name}")
    print()
    print(f"  仓库链接：")
    print(f"    https://github.com/{username}/{repo_name}")
    print()
    print("  📅 明天早上 8:05，你的钉钉群会收到第一份日报！")
    print()
    print("  📌 你也可以手动触发一次测试：")
    print(f"    打开仓库 → Actions → 钉钉日报 → Run workflow")
    print()
    print("  💡 有问题找我：中科汇航 · 王玉川")
    print("=" * 60)


if __name__ == "__main__":
    main()
