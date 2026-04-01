(function(){
  if (window.dashboardData) {
    const statuses = window.dashboardData.statuses || [];
    const payments = window.dashboardData.payment_methods || [];
    const sctx = document.getElementById('statusChart');
    const pctx = document.getElementById('paymentChart');
    if (sctx) new Chart(sctx, {type:'doughnut', data:{labels:statuses.map(x=>x[0]), datasets:[{data:statuses.map(x=>x[1])}]}});
    if (pctx) new Chart(pctx, {type:'bar', data:{labels:payments.map(x=>x[0]), datasets:[{label:'Оплаты',data:payments.map(x=>x[1])}]}});
  }
})();
