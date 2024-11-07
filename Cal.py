def Cal():
    history = []
    while True:
        ini_m = input("请输入初始余额:")
        try:
            m = float(ini_m)
            break
        except ValueError:
            print("输入有效数字")

    while True:
        cost = input("请输入收支(在金额前加'+'表示收入,否则默认为支出;输入'undo'撤销上一次操作):")
        if not cost.strip():
            break
        if cost.lower() == 'undo':
            if history:
                last_change = history.pop()
                m -= last_change
                print(f"已撤销上一次操作，当前余额:{m:.2f}")
            else:
                print("没有可撤销的操作")
            continue

        try:
            if cost[0] == '+':
                cost = float(cost[1:].strip())
                m += cost
                history.append(cost)
            else:
                cost = float(cost.strip())
                m -= cost
                history.append(-cost)
            print(f"当前余额:{m:.2f}")
        except ValueError:
            print("请输入有效数字")
    return m


cal = Cal()
print(f"最终结果是:{cal:.2f}")
