# 宣告為假目標：避免與同名資料夾（test/ data/ ui/ 等）衝突，確保每次都執行 recipe
.PHONY: chain deploy data demo api ui test

chain:      ; npx hardhat node
deploy:     ; npx hardhat run scripts/deploy.js --network localhost
data:       ; python -m data.synth_fleet --ships 30 --months 12 && python -m data.build_requests
demo:       ; python -m backend.demo
api:        ; uvicorn backend.api:app --reload --port 8000
ui:         ; python -m http.server 5500 --directory ui
test:       ; npx hardhat test
