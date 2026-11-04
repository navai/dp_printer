# -*- coding: utf-8 -*-
"""
单采系统两个真实标签模板 —— 从阳信系统前端源码 src/api/donor.js 逐行移植
（printDonorInfoByRegisterNo / printPlasmaInfoForPrintLabel）
"""
from engine import Job

# ================================================================ 1. 浆员登记标签 50×50mm
def print_donor_label(info: dict, copies: int = 1) -> Job:
    """
    info 字段（与前端 donPrintinfo 一致）:
      No / NAME / type / nowDate / age / sex / x / e / registerNo
    """
    LODOP = Job(task="浆员登记标签打印")

    LODOP.PRINT_INITA(0, 0, 500, 500, "浆员登记标签打印")
    LODOP.SET_PRINT_PAGESIZE(1, "50mm", "50mm")
    LODOP.ADD_PRINT_TEXT(6, 6, 105, 20, info["No"]);            LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(6, 88, 53, 20, info["NAME"]);          LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(6, 137, 65, 20, info["type"]);         LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(27, 14, 89, 20, info["nowDate"]);      LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(27, 89, 36, 20, info["age"]);          LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(27, 125, 29, 20, info["sex"]);         LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(27, 158, 21, 20, info["x"]);           LODOP.SET_PRINT_STYLEA(0, "FontSize", 10)
    LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(27, 175, 19, 20, info["e"]);           LODOP.SET_PRINT_STYLEA(0, "FontSize", 10)
    LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(27, 158, 31, 20, "");                  LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_BARCODE(51, 19, 211, 45, "128A", info["registerNo"])
    LODOP.ADD_PRINT_TEXT(98, 10, 96, 20, "开采:_______");       LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(98, 107, 96, 20, "结束:_______");      LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(120, 10, 96, 20, "体外:_______");      LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(118, 107, 96, 20, "抗凝:_______");     LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(144, 10, 96, 20, "次数:_______");      LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(144, 107, 96, 20, "浆量:______g");     LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    if copies > 1:
        LODOP.SET_PRINT_COPIES(copies)
    LODOP.PRINTB()
    return LODOP


# ================================================================ 2. 血浆标签 90×120mm
def print_plasma_label(info: dict) -> Job:
    """
    info 字段（与前端 printinfo 一致）:
      seriesNo / donorName / plasmaType / collectNo / y / donorNo /
      bloodType / collectDate / registerNo / weight / plasmaTypeLabel /
      siteName / validDate / elc
    """
    LODOP = Job(task="血浆标签打印")
    p = info

    LODOP.PRINT_INITA(0, 0, 900, 1200, "血浆标签打印")
    LODOP.SET_PRINT_MODE("PRINT_NOCOLLATE", 1)
    LODOP.SET_PRINT_PAGESIZE(1, "90mm", "120mm")
    LODOP.ADD_PRINT_TEXT(40, 11, 30, 20, p["seriesNo"])
    LODOP.ADD_PRINT_TEXT(40, 50, 58, 20, p["donorName"])
    LODOP.ADD_PRINT_TEXT(41, 141, 20, 20, p["plasmaType"])
    LODOP.ADD_PRINT_BARCODE(54, 32, 160, 50, "128A", p["collectNo"])
    LODOP.ADD_PRINT_TEXT(6, 184, 30, 20, p["seriesNo"])
    LODOP.ADD_PRINT_TEXT(6, 232, 58, 20, p["donorName"])
    LODOP.ADD_PRINT_TEXT(8, 297, 70, 22, p["plasmaType"] + p["y"])
    LODOP.ADD_PRINT_BARCODE(21, 203, 160, 52, "128A", p["collectNo"])
    LODOP.ADD_PRINT_TEXT(109, 11, 30, 20, p["seriesNo"])
    LODOP.ADD_PRINT_TEXT(109, 50, 63, 20, p["donorName"])
    LODOP.ADD_PRINT_TEXT(109, 141, 20, 20, p["plasmaType"])
    LODOP.ADD_PRINT_BARCODE(124, 32, 160, 50, "128A", p["collectNo"])
    LODOP.ADD_PRINT_TEXT(84, 184, 34, 25, p["seriesNo"])
    LODOP.ADD_PRINT_TEXT(84, 232, 58, 25, p["donorName"])
    LODOP.ADD_PRINT_TEXT(84, 315, 21, 25, p["plasmaType"])
    LODOP.ADD_PRINT_BARCODE(100, 203, 160, 70, "128A", p["collectNo"])
    LODOP.ADD_PRINT_TEXT(197, 14, 38, 20, p["seriesNo"]);       LODOP.SET_PRINT_STYLEA(0, "FontSize", 11)
    LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(246, 23, 131, 20, "姓名:" + p["donorName"]);   LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(246, 166, 160, 20, "浆员卡号:" + p["donorNo"]); LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(267, 23, 130, 25, "血型:" + p["bloodType"]);   LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(269, 166, 160, 25, "采浆日期:" + p["collectDate"]); LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(292, 23, 180, 20, "流水号：" + p["registerNo"]); LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(292, 166, 160, 20, "采浆量：" + p["weight"]);   LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(312, 166, 160, 25, "血浆类型：" + p["plasmaTypeLabel"]); LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_BARCODE(337, 40, 227, 65, "128A", p["collectNo"])
    LODOP.ADD_PRINT_TEXT(350, 263, 48, 35, p["plasmaType"]);    LODOP.SET_PRINT_STYLEA(0, "FontSize", 25)
    LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(223, 78, 177, 20, "本血浆只适合生产使用")
    LODOP.SET_PRINT_STYLEA(0, "Alignment", 2); LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(196, 91, 142, 25, "原料血浆");          LODOP.SET_PRINT_STYLEA(0, "FontSize", 12)
    LODOP.SET_PRINT_STYLEA(0, "Alignment", 2); LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(408, 76, 154, 20, p["siteName"]);      LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(428, 40, 100, 25, "-20℃以下存储");     LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(428, 164, 146, 23, "有效期至：" + p["validDate"]); LODOP.SET_PRINT_STYLEA(0, "Bold", 1)
    LODOP.ADD_PRINT_TEXT(80, 206, 26, 31, p["elc"]);            LODOP.SET_PRINT_STYLEA(0, "FontSize", 12)
    LODOP.PRINTB()
    return LODOP


SAMPLE_DONOR = {
    "No": "A0001", "NAME": "张三", "type": "普通", "nowDate": "2026-11-04",
    "age": "32", "sex": "男", "x": "O", "e": "型", "registerNo": "P20261104001",
}

SAMPLE_PLASMA = {
    "seriesNo": "000123", "donorName": "张三", "plasmaType": "普通",
    "collectNo": "P20261104001", "y": "浆", "donorNo": "K00012345",
    "bloodType": "O型", "collectDate": "2026-11-04", "registerNo": "P20261104001",
    "weight": "580g", "plasmaTypeLabel": "普通血浆", "siteName": "某某单采血浆站",
    "validDate": "2027-11-04", "elc": "电泳:—",
}

if __name__ == "__main__":
    import os, sys
    sys.stdout.reconfigure(encoding="utf-8")
    out = os.path.join(os.path.dirname(__file__), "out")
    os.makedirs(out, exist_ok=True)
    for fn, name in [(print_donor_label, "donor_label"), (print_plasma_label, "plasma_label")]:
        j = fn(SAMPLE_DONOR if "donor" in name else SAMPLE_PLASMA)
        png = os.path.join(out, f"preview_{name}.png")
        j.render_image(600).save(png)      # 预览用 600dpi 更清晰
        print("渲染完成:", png, "| warnings:", j.warnings)
