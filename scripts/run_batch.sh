uv run python scripts/batch_runner.py \
	--dataset junyeong-nero/korean-online-mind2web \
	--limit 500 \
	--workers 4 \
	--metadata-initial-url \
	--log-agent \
	--extra-arg=--stealth \
	--extra-arg=--locale=ko-KR \
	--extra-arg=--timezone=Asia/Seoul \
	'--extra-arg=--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
