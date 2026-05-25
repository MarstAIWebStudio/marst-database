const MarstDB = {
    init(config) {
        const API = 'https://marst-database.onrender.com';
        const apiKey = config.apiKey;

        return {
            // DB
            db: {
                // 조회
                get: async (collection) => {
                    const res = await fetch(`${API}/api/db/${collection}`, {
                        headers: { 'X-API-Key': apiKey }
                    });
                    return await res.json();
                },

                // 저장
                set: async (collection, data) => {
                    const res = await fetch(`${API}/api/db/${collection}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-API-Key': apiKey
                        },
                        body: JSON.stringify(data)
                    });
                    return await res.json();
                },

                // 수정
                update: async (collection, id, data) => {
                    const res = await fetch(`${API}/api/db/${collection}/${id}`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-API-Key': apiKey
                        },
                        body: JSON.stringify(data)
                    });
                    return await res.json();
                },

                // 삭제
                delete: async (collection, id) => {
                    const res = await fetch(`${API}/api/db/${collection}/${id}`, {
                        method: 'DELETE',
                        headers: { 'X-API-Key': apiKey }
                    });
                    return await res.json();
                }
            },

            // 인증
            auth: {
                register: async (username, password, email) => {
                    const res = await fetch(`${API}/api/register`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username, password, email })
                    });
                    return await res.json();
                },

                login: async (username, password) => {
                    const res = await fetch(`${API}/api/login`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username, password })
                    });
                    const data = await res.json();
                    if (data.token) {
                        localStorage.setItem('marst_token', data.token);
                        localStorage.setItem('marst_user', JSON.stringify({
                            username: data.username,
                            role: data.role
                        }));
                    }
                    return data;
                },

                logout: () => {
                    localStorage.removeItem('marst_token');
                    localStorage.removeItem('marst_user');
                },

                currentUser: () => JSON.parse(localStorage.getItem('marst_user') || 'null'),
                isLoggedIn: () => !!localStorage.getItem('marst_token')
            }
        };
    }
};