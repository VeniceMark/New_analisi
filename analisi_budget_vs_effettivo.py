```html
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analisi Budget vs Effettivo</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --primary: #3b82f6;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #8b5cf6;
            --dark: #1e293b;
            --light: #f8fafc;
            --gray: #94a3b8;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        body {
            background-color: #f1f5f9;
            color: #334155;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: white;
            padding: 2rem 0;
            text-align: center;
            border-radius: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }
        
        .subtitle {
            font-size: 1.2rem;
            opacity: 0.9;
        }
        
        .card {
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #e2e8f0;
        }
        
        h2 {
            color: #334155;
            font-size: 1.5rem;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }
        
        th, td {
            padding: 0.75rem;
            text-align: center;
            border: 1px solid #e2e8f0;
        }
        
        th {
            background-color: #f1f5f9;
            font-weight: 600;
        }
        
        .positive {
            background-color: #dcfce7;
            color: #166534;
        }
        
        .negative {
            background-color: #fee2e2;
            color: #991b1b;
        }
        
        .extrabudget {
            background-color: #ddd6fe;
            color: #5b21b6;
        }
        
        .zero {
            background-color: #1e293b;
            color: white;
        }
        
        .chart-container {
            height: 400px;
            margin-top: 1rem;
        }
        
        .legend {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 1rem;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 3px;
        }
        
        .budget-color {
            background-color: #3b82f6;
        }
        
        .actual-color {
            background-color: #10b981;
        }
        
        .extra-color {
            background-color: #8b5cf6;
        }
        
        footer {
            text-align: center;
            padding: 2rem 0;
            color: var(--gray);
            font-size: 0.9rem;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            h1 {
                font-size: 2rem;
            }
            
            th, td {
                padding: 0.5rem;
                font-size: 0.85rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Analisi Budget vs Effettivo</h1>
            <p class="subtitle">Confronto dettagliato delle ore lavorate previste e reali</p>
        </header>
        
        <div class="card">
            <div class="card-header">
                <h2>📊 Scostamento Percentuale</h2>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Cliente</th>
                            <th>2025-07 (1-15)</th>
                            <th>2025-07 (1-31)</th>
                            <th>2025-08 (1-15)</th>
                            <th>2025-08 (1-31)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Cliente A</td>
                            <td class="positive">+25%</td>
                            <td class="negative">-10%</td>
                            <td class="positive">+5%</td>
                            <td class="extrabudget">Extrabudget</td>
                        </tr>
                        <tr>
                            <td>Cliente B</td>
                            <td class="negative">-30%</td>
                            <td class="negative">-15%</td>
                            <td class="positive">+20%</td>
                            <td class="zero">0%</td>
                        </tr>
                        <tr>
                            <td>Cliente C</td>
                            <td class="extrabudget">Extrabudget</td>
                            <td class="positive">+12%</td>
                            <td class="negative">-8%</td>
                            <td class="positive">+3%</td>
                        </tr>
                        <tr>
                            <td>Cliente D</td>
                            <td class="zero">0%</td>
                            <td class="zero">0%</td>
                            <td class="zero">0%</td>
                            <td class="zero">0%</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h2>📋 Dati Dettagliati</h2>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th rowspan="2">Cliente</th>
                            <th colspan="3">2025-07 (1-15)</th>
                            <th colspan="3">2025-08 (1-31)</th>
                        </tr>
                        <tr>
                            <th>Effettivo</th>
                            <th>Budget</th>
                            <th>%</th>
                            <th>Effettivo</th>
                            <th>Budget</th>
                            <th>%</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Cliente A</td>
                            <td>120</td>
                            <td>100</td>
                            <td class="positive">+20%</td>
                            <td>85</td>
                            <td>100</td>
                            <td class="negative">-15%</td>
                        </tr>
                        <tr>
                            <td>Cliente B</td>
                            <td>70</td>
                            <td>100</td>
                            <td class="negative">-30%</td>
                            <td>0</td>
                            <td>0</td>
                            <td class="zero">0%</td>
                        </tr>
                        <tr>
                            <td>Cliente C</td>
                            <td>0</td>
                            <td>0</td>
                            <td class="zero">0%</td>
                            <td>95</td>
                            <td>80</td>
                            <td class="positive">+18.75%</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h2>📈 Dashboard Riepilogativa</h2>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Cliente</th>
                            <th>Ore Effettive</th>
                            <th>Ore a Budget</th>
                            <th>Scostamento %</th>
                            <th>Scostamento Valore</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Cliente A</td>
                            <td>205</td>
                            <td>200</td>
                            <td class="positive">+2.5%</td>
                            <td class="positive">+5</td>
                        </tr>
                        <tr>
                            <td>Cliente B</td>
                            <td>70</td>
                            <td>100</td>
                            <td class="negative">-30%</td>
                            <td class="negative">-30</td>
                        </tr>
                        <tr>
                            <td>Cliente C</td>
                            <td>95</td>
                            <td>80</td>
                            <td class="positive">+18.75%</td>
                            <td class="extrabudget">15</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h2>📉 Grafico a Barre</h2>
            </div>
            <div class="chart-container">
                <canvas id="barChart"></canvas>
            </div>
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color budget-color"></div>
                    <span>Budget</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color actual-color"></div>
                    <span>Effettivo</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color extra-color"></div>
                    <span>Extrabudget</span>
                </div>
            </div>
        </div>
        
        <footer>
            <p>Analisi Budget vs Effettivo - Sistema di monitoraggio delle performance</p>
        </footer>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const ctx = document.getElementById('barChart').getContext('2d');
            
            // Dati di esempio per il grafico
            const data = {
                labels: ['Cliente A', 'Cliente B', 'Cliente C', 'Cliente D'],
                datasets: [
                    {
                        label: 'Budget',
                        data: [200, 100, 80, 0],
                        backgroundColor: '#3b82f6',
                        borderColor: '#2563eb',
                        borderWidth: 1
                    },
                    {
                        label: 'Effettivo',
                        data: [205, 70, 80, 0],
                        backgroundColor: '#10b981',
                        borderColor: '#059669',
                        borderWidth: 1
                    },
                    {
                        label: 'Extrabudget',
                        data: [0, 0, 15, 0],
                        backgroundColor: '#8b5cf6',
                        borderColor: '#7c3aed',
                        borderWidth: 1
                    }
                ]
            };
            
            const config = {
                type: 'bar',
                data: data,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Ore'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Clienti'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `${context.dataset.label}: ${context.parsed.y} ore`;
                                }
                            }
                        }
                    }
                }
            };
            
            const barChart = new Chart(ctx, config);
        });
    </script>
</body>
</html>
```
