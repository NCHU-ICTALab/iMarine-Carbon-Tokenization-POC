# iMarine · 港口碳權代幣化 PoC

> 2026 航港大數據創意應用競賽參賽作品

把船舶超額減碳（Surplus Unit, SU）鑄成鏈上代幣，可掛單交易、可為特定用途除役銷毀，全程留下可稽核事件。這是 **TCX 海運合規專區藍圖裡「未來 RWA 層」的可運作雛形**。

---

## 專案定位

台灣不是 IMO 會員國，卻躲不掉國際碳定價與供應鏈（Scope 3）的減碳要求。本專案示範一條可行路徑：由航港局主導，將經第三方驗證的船舶超額減碳登錄、上鏈、並支援 book-and-claim 式的碳權移轉。目標不是產品，而是一個「從鏈到 UI 都能實際跑起來」的可展示雛形。

## 核心概念

以 **Surplus Unit (SU)** 為核心資產，四個動作 + 兩個限制：

- **發行 (mint)**：由核發者依驗證後的超額減碳量鑄造，附帶鏈下明細的雜湊（`dataHash`）防竄改。
- **交易 (list / buy)**：於市場合約掛單，付款與代幣移轉在同一筆交易原子交割。
- **除役 (retire)**：持有者為特定用途（如 Scope 3 抵減）銷毀代幣並留下用途標籤。
- **限制**：每單位**只能真正轉讓一次**、且**逾期不可轉讓**——貼近碳權「用一次就消耗」的性質。

## 系統架構

四層、層間以明確介面解耦，任一層可獨立替換：

```
UI 層          單一 HTML + 原生 JS，只消費後端 REST
  ↓ REST
後端/媒介層     web3.py + FastAPI：送交易 / 聽事件 / 管金鑰 / 開 API
  ↑ 讀
資料介面層      能耗資料 → 碳強度(GFI)/超額量計算 → 驗證 → 標準化鑄造請求 + dataHash
  ↑ 讀
鏈層           Solidity + Hardhat：SurplusUnit(ERC-721) / Market / MockStablecoin
```

設計圍繞三個原則：**可遷移**（環境相關設定集中、程式碼不寫死）、**可擴展**（抽象介面與角色控制，加功能只加不改）、**可維護**（單一職責、單一設定入口、測試先行）。

## 技術棧

| 層 | 技術 |
|---|---|
| 鏈層 | Solidity 0.8.24、Hardhat 2.x、OpenZeppelin Contracts v5 |
| 資料層 | Python 3.11+、pandas |
| 後端 | Python、web3.py、FastAPI |
| UI | 原生 HTML + JavaScript |

## 快速開始

需求：Node.js LTS ≥ 20、**Python ≥ 3.11**（若系統 `python3` 較舊，用 pyenv 等建一個 3.11+ 的 venv）。

```bash
# 1) 安裝相依
npm install
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                 # 本地測試金鑰已在範本內（僅限本地）

# 2) 產生執行期產物（三個介面檔，都是 gitignore、需自行產生）
#    終端機 A（會佔用）：
make chain                           # 啟動本地 Hardhat 鏈
#    終端機 B：
make deploy                          # 部署三合約 + 匯出 shared/contracts.localhost.json
make data                            # 產出 data/out/minting_requests.json（108 筆 / 414,312 噸）

# 3) 端到端看整條流程（擇一）
make demo                            # 純腳本：印某 SU 的 held → listed → sold → retired
make api                             # 或開 API（:8000），瀏覽 http://127.0.0.1:8000/docs
```

> 一鍵指令對照見 `Makefile`（`make test` 跑合約單元測試、`make test-backend` 跑後端整合測試）。

## 目前進度（白話版）

專案分四層，一層一層做、每層都要通過測試才算完成。目前狀態：

- **鏈層（智能合約）— 完成。** 碳權憑證（SU）的鏈上規則全部寫好、單元測試 5/5 全綠：發行、只能真正轉手一次、到期失效、除役銷毀、市場「一手交錢一手交券」的原子交割。
- **資料層（資料處理）— 完成。** 能把船舶能耗資料換算成「超額減碳噸數」，只有真的超額的船才發券，並替每筆產生防竄改指紋（`dataHash`）。用示範資料（30 艘船 × 12 個月）跑出 108 張可鑄券、合計 414,312 噸。
- **後端 — 完成。** 把上面兩層串起來、對外開 API：批次發行、上架、購買、除役全流程可跑，本地帳本從鏈上事件同步，並提供 `/verify` 端點回驗鏈上指紋與鏈下明細一致。整合測試通過、`make demo` 走完 SU 一生。
- **UI — 未開始（下一步）。** 一個能點按鈕、看整條流程跑的網頁。

> 上面兩層在合併進主線前，都先跑過測試並做過一輪多角度審查（確認測試沒有被灌水、合約的安全性質確實成立）。

## 規劃目錄結構

```
contracts/   鏈層合約（SurplusUnit / Market / MockStablecoin）
test/        合約單元測試
scripts/     部署腳本
shared/      鏈層 → 後端的介面檔（部署後自動產生）
data/        資料介面層（資料來源 adapter、計算、驗證、鑄造請求）
backend/     後端媒介層（chain client、本地帳本、服務、API）
ui/          流程觀察前端
```

## 建置順序（Roadmap）

1. [完成] 鏈層：三份合約 + 單元測試全綠
2. [完成] 部署腳本：產出 `shared/` 介面檔
3. [完成] 資料層：產出標準化鑄造請求
4. [完成] 後端：端到端流程（發行 → 上架 → 售出 → 除役）+ REST API + `/verify` 防竄改回驗
5. [ ] UI：可視化流程觀察（只打後端 REST）

## 授權

待定（合約程式碼採 MIT，見各 `.sol` 檔 SPDX 標頭）。
