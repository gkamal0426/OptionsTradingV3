
async function handleLogin() {
    
    const index = document.getElementById('indexSelect').value;
    const account = document.getElementById('accountSelect').value;
    const oldtwofaCode = document.getElementById('oldtwofaInput').value;
    const newtwofaCode = document.getElementById('newtwofaInput').value;
    const confirmed = document.getElementById('confirmCheck').checked;
    
    
    if (!confirmed) {
        alert('⚠️ Please confirm that you want to trade with the selected index.');
        return;
    }
    
    
    if (account === 'client2') {
        if (!oldtwofaCode || oldtwofaCode.length !== 6) {
            alert('⚠️ Please enter a valid 6-digit 2FA code for Old User.');
            document.getElementById('oldtwofaInput').focus();
            return;
        }
    } 
    else if (account === 'client1') {
        if (!newtwofaCode || newtwofaCode.length !== 6) {
            alert('⚠️ Please enter a valid 6-digit 2FA code for New User.');
            document.getElementById('newtwofaInput').focus();
            return;
        }
    } 
    else if (account === 'both') {
        if (!oldtwofaCode || oldtwofaCode.length !== 6) {
            alert('⚠️ Please enter a valid 6-digit 2FA code for Old User.');
            document.getElementById('oldtwofaInput').focus();
            return;
        }
        if (!newtwofaCode || newtwofaCode.length !== 6) {
            alert('⚠️ Please enter a valid 6-digit 2FA code for New User.');
            document.getElementById('newtwofaInput').focus();
            return;
        }
    }
    
    
    const indexNames = {
        '1': 'SENSEX',
        '26000': 'NIFTY',
        '26009': 'BANKNIFTY'
    };
    const indexName = indexNames[index];
    
    
    document.getElementById('loadingModal').style.display = 'flex';
    document.getElementById('loadingMessage').textContent = 
        `Logging in as ${account} for ${indexName}...`;
    
    try {
        
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                account: account,
                index: parseInt(index),
                client2twofa_code: oldtwofaCode,
                client1twofa_code: newtwofaCode
            })
        });
        
        
        const result = await response.json();
        
        
        if (result.status === 'success') {
            
            document.getElementById('loadingMessage').textContent = 
                '✅ Login Successful! Redirecting...';
            
            
            setTimeout(() => {
                console.log('Redirecting to:', result.redirect);
                window.location.href = result.redirect;
            }, 1000);
            
        } else {
            
            document.getElementById('loadingModal').style.display = 'none';
            alert('❌ ' + result.message);
        }
        
    } catch (error) {
       
        document.getElementById('loadingModal').style.display = 'none';
        console.error('Login error:', error);
        alert('❌ Network error. Please check your connection and try again.');
    }
}

document.addEventListener('keypress', function(event) {
    if (event.key === 'Enter') {
        handleLogin();
    }
});


document.getElementById('oldtwofaInput').addEventListener('input', function(e) {
    this.value = this.value.replace(/[^0-9]/g, '');
});


document.getElementById('newtwofaInput').addEventListener('input', function(e) {
    this.value = this.value.replace(/[^0-9]/g, '');
});


window.addEventListener('load', function() {
    document.getElementById('oldtwofaInput').value = '';
    document.getElementById('newtwofaInput').value = '';
    document.getElementById('confirmCheck').checked = false;
});


document.getElementById('accountSelect').addEventListener('change', function() {
    const account = this.value;
    const oldGroup = document.getElementById('oldtwofaGroup')
    const newGroup = document.getElementById('newtwofaGroup')
    if (account === 'client2') {
        oldGroup.style.display = 'block';
        newGroup.style.display = 'none';
    } else if (account === 'client1') {
        oldGroup.style.display = 'none';
        newGroup.style.display = 'block';
    } else if (account === 'both') {
        oldGroup.style.display = 'block';
        newGroup.style.display = 'block';
    }
});


window.addEventListener('DOMContentLoaded', function() {
    document.getElementById('accountSelect').dispatchEvent(new Event('change'));
});
