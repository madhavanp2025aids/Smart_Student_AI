// Handle Enter key in chat input
function handleKeyPress(event) {
	if (event.key === 'Enter' && !event.shiftKey) {
		event.preventDefault();
		sendMessage();
	}
}

// Show toast notification
function showToast(message, type = 'success') {
	const toast = document.createElement('div');
	toast.textContent = message;
	toast.style.cssText = `position: fixed; top: 20px; right: 20px; background: ${type === 'success' ? '#667eea' : '#f44336'}; color: white; padding: 15px 25px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 9999;`;
	document.body.appendChild(toast);
	setTimeout(() => {
		toast.style.animation = 'slideOut 0.3s ease-out';
		setTimeout(() => toast.remove(), 300);
	}, 3000);
}

async function getCareer() {
	const selectedSkills = Array.from(document.querySelectorAll('.skill-checkbox:checked')).map(el => el.value);
	if (selectedSkills.length === 0) {
		showToast('Please select at least one skill!', 'error');
		return;
	}
	const resultDiv = document.getElementById('careerResult');
	resultDiv.innerHTML = '<div class="loading"></div>';
	resultDiv.classList.add('show');
	try {
		const res = await fetch('/career', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ skills: selectedSkills })
		});
		const data = await res.json();
		const careers = data.careers || [];
		
		let cardsHTML = '<div style="margin-top: 20px;"><p style="font-weight: 600; color: #ff006e; font-size: 1.1rem; margin-bottom: 15px;">🚀 Recommended Career Paths</p>';
		cardsHTML += '<div class="career-cards-grid">';
		
		careers.forEach(career => {
			cardsHTML += `
				<div class="career-card-detailed">
					<div class="career-header">
						<span class="career-emoji">${career.emoji}</span>
						<h3 class="career-name">${career.name}</h3>
					</div>
					<p class="career-description">${career.description}</p>
					<div class="career-info">
						<div class="info-item">
							<span class="info-label">💰 Salary:</span>
							<span class="info-value">${career.salary_range}</span>
						</div>
						<div class="info-item">
							<span class="info-label">📈 Growth:</span>
							<span class="info-value">${career.growth}</span>
						</div>
					</div>
				</div>
			`;
		});
		
		cardsHTML += '</div></div>';
		resultDiv.innerHTML = cardsHTML;
		showToast(`Found ${careers.length} career recommendations!`, 'success');
	} catch (error) {
		resultDiv.innerHTML = '<p>Error loading. Please try again.</p>';
		showToast('Error loading recommendation', 'error');
	}
}

async function getStudy() {
	const noise = document.getElementById('noise').value;
	const focus = document.getElementById('focus').value;
	const subject = document.getElementById('subject').value;
	const lighting = document.getElementById('lighting').value;
	const temperature = document.getElementById('temperature').value;
	const resultDiv = document.getElementById('studyResult');
	resultDiv.innerHTML = '<div class="loading"></div>';
	resultDiv.classList.add('show');
	try {
		const res = await fetch('/study', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ 
				noise: noise, 
				focus: focus, 
				subject: subject,
				lighting: lighting,
				temperature: temperature
			})
		});
		const data = await res.json();
		const recommendations = data.recommendations || [];
		const bonusTips = data.bonus_tips || null;
		const environmentConclusion = data.environment_conclusion || null;
		
		// Start with environment conclusion card
		let cardsHTML = '<div style="margin-top: 20px;">';
		
		// Display prominent environment conclusion
		if (environmentConclusion) {
			cardsHTML += `
				<div class="environment-conclusion-card">
					<div class="conclusion-emoji">${environmentConclusion.emoji}</div>
					<h2 class="conclusion-title">Your Perfect Study Space</h2>
					<h3 class="conclusion-name">${environmentConclusion.name}</h3>
					<p class="conclusion-description">${environmentConclusion.description}</p>
				</div>
			`;
		}
		
		// Then recommendations
		cardsHTML += '<p style="font-weight: 600; color: #ff006e; font-size: 1.1rem; margin-bottom: 15px; margin-top: 30px;">✨ Detailed Recommendations</p>';
		cardsHTML += '<div class="study-cards-grid">';
		
		recommendations.forEach(rec => {
			cardsHTML += `
				<div class="study-card-detailed">
					<div class="study-header">
						<span class="study-emoji">${rec.emoji}</span>
						<h3 class="study-category">${rec.category}</h3>
					</div>
					<h4 class="study-name">${rec.name}</h4>
					<p class="study-description">${rec.description}</p>
					<div class="study-info">
						<div class="info-item">
							<span class="info-label">📌 Best For:</span>
							<span class="info-value">${rec.best_for}</span>
						</div>
						<div class="info-item">
							<span class="info-label">💡 Note:</span>
							<span class="info-value">${rec.notes}</span>
						</div>
					</div>
				</div>
			`;
		});
		
		cardsHTML += '</div>';
		
		// Add bonus tips if available
		if (bonusTips && bonusTips.tips && bonusTips.tips.length > 0) {
			cardsHTML += '<div style="margin-top: 20px;"><p style="font-weight: 600; color: #667eea; font-size: 1rem; margin-bottom: 10px;">🎯 Pro Tips For You</p>';
			cardsHTML += '<div class="bonus-tips">';
			bonusTips.tips.forEach(tip => {
				cardsHTML += `<div class="tip-item">${tip}</div>`;
			});
			cardsHTML += '</div></div>';
		}
		
		cardsHTML += '</div>';
		resultDiv.innerHTML = cardsHTML;
		showToast(`Found ${recommendations.length} study recommendations!`, 'success');
	} catch (error) {
		resultDiv.innerHTML = '<p>Error loading. Please try again.</p>';
		showToast('Error loading recommendation', 'error');
	}
}

async function sendMessage() {
	const userInput = document.getElementById('userInput').value.trim();
	if (!userInput) {
		showToast('Please type a message!', 'error');
		return;
	}
	const chatbox = document.getElementById('chatbox');
	
	// User message (instant display - 0ms)
	const userMsg = document.createElement('div');
	userMsg.className = 'message-wrapper user-wrapper';
	userMsg.innerHTML = '<div class="user-message"><span class="msg-label">👤 You:</span><span class="msg-text">' + userInput + '</span></div>';
	chatbox.appendChild(userMsg);
	document.getElementById('userInput').value = '';
	chatbox.scrollTop = chatbox.scrollHeight;
	
	// Show AI response container IMMEDIATELY (no loading state)
	const aiMsg = document.createElement('div');
	aiMsg.className = 'message-wrapper ai-wrapper lightning-fast';
	const textContainer = document.createElement('span');
	textContainer.className = 'msg-text-container';
	aiMsg.innerHTML = '<div class="ai-message"><span class="msg-label">⚡ AI (Ultra-Fast):</span></div>';
	aiMsg.querySelector('.ai-message').appendChild(textContainer);
	chatbox.appendChild(aiMsg);
	
	try {
		// Always use streaming - it's now the fastest approach
		const res = await fetch('/chat_stream', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ message: userInput })
		});
		
		if (!res.ok) throw new Error("Stream failed");
		
		const reader = res.body.getReader();
		const decoder = new TextDecoder();
		let fullResponse = '';
		let emoji = '⚡';
		
		let isFirstChunk = true;
		
		try {
			while (true) {
				const { done, value } = await reader.read();
				if (done) break;
				
				const chunk = decoder.decode(value);
				const lines = chunk.split('\n').filter(l => l.trim());
				
				for (const line of lines) {
					try {
						const data = JSON.parse(line);
						if (data.emoji) {
							emoji = data.emoji;
							aiMsg.querySelector('.msg-label').textContent = emoji + ' AI Response:';
						} else if (data.chunk) {
							// Show response immediately (no delay)
							if (isFirstChunk) {
								isFirstChunk = false;
								aiMsg.classList.add('response-received');
							}
							fullResponse += data.chunk;
							textContainer.textContent = fullResponse;
							textContainer.classList.add('typing');
							chatbox.scrollTop = chatbox.scrollHeight;
						}
					} catch (e) {}
				}
			}
		} catch (streamError) {
			// Response captured, continue
		}
		
		// Remove typing indicator when done
		textContainer.classList.remove('typing');
		
	} catch (error) {
		// Fallback: Use standard fast endpoint
		try {
			const res = await fetch('/chat', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ message: userInput })
			});
			const data = await res.json();
			
			const emoji = data.emoji || '⚡';
			textContainer.textContent = data.reply;
			aiMsg.querySelector('.msg-label').textContent = emoji + ' AI Response:';
			aiMsg.classList.add('response-received');
			chatbox.scrollTop = chatbox.scrollHeight;
		} catch (fallbackError) {
			textContainer.textContent = '⚡ Quick tip: Break learning into small chunks, practice daily, and review regularly!';
		}
	}
}
