/*
 * JavaScript code to support the AuroraWatchNet summary browser.
 *
 */

var reloadInterval_ms = 3 * 60 * 1000;
var reloadRollingID = null;
var reloadTodayID = null;


function cancelReloadRolling() {
  if (reloadRollingID !== null) {
    // Cancel timer which reloads rolling plots
    window.clearInterval(reloadRollingID);
    reloadRollingID = null;
  }
  return true;
};

function cancelReloadToday() {
  if (reloadTodayID !== null) {
    // Cancel timer which reloads today's plots
    window.clearInterval(reloadTodayID);
    reloadTodayID = null;
  }
  return true;
};

// Initialise the webpage. Do this only after the webpage which
// included gaia_viewer.js has finished loading.
function bodyOnLoad() {
  // Create a date control
  var dcOpts = { 
    "utc": true,
    "immediateUpdate": false,
    "callback": function (t) { 
      loadDailyPlots(t.getDate()); },
    "date": gaiaDate.getUTCToday(),
    "earliestDate": new Date(Date.UTC(2012, 0 ,1)),
    "latestDate": gaiaDate.getUTCToday(),
    "disabled": true
  };
    
  var dc = new gaiaDate.dateControl(dcOpts);
    
  // Add the date controls.
  document.getElementById('date-year').appendChild(dc.yearControl());
  document.getElementById('date-month').appendChild(dc.monthControl());
  document.getElementById('date-dom').appendChild(dc.domControl());
  document.getElementById('date-prev-day').appendChild(dc.incrementControl('-1 day', -86400e3, true));
  document.getElementById('date-next-day').appendChild(dc.incrementControl('+1 day', +86400e3, true));
  document.getElementById('date-go').appendChild(dc.submitControl('Go'));

    
  // Enable the controls
  dc.setDisabled(false);
  loadRollingPlots();
  return true;
};

function loadDailyPlots(t) {
  if(typeof t == 'undefined')
    // If called with no arguments then set "t" to be today.
    t = gaiaDate.getUTCToday();
  
  if (t > gaiaDate.getUTCToday())
    // Do not attempt to show future plots
    return true;
  
  cancelReloadRolling();

  var uniq = '';
  if (t.valueOf() == gaiaDate.getUTCToday().valueOf()) {
    if (reloadTodayID === null)
      // Don't pass the date when setting up the interval timer, let
      // the function compute it when called. This will ensure the new
      // day gets loaded after midnight.
      reloadTodayID = window.setInterval(loadDailyPlots, reloadInterval_ms);
    uniq = '?' + Date.now();
  }
  else
    cancelReloadToday();
  
  var urlParts = window.location.pathname.split('/');
  var site = urlParts[urlParts.length - 2];
  if (site == 'stackplots') {
    document.getElementById('img-stackplot').src 
      = gaiaDate.strftime(t, '%Y/%m/%Y%m%d.png') + uniq;
    document.getElementById('div-stackplot').style.visibility = 'visible';
    document.getElementById('div-site-plots').style.visibility = 'hidden';
  }
  else {
    document.getElementById('img-magnetometer').src 
      = gaiaDate.strftime(t, '%Y/%m/' + site + '_%Y%m%d.png') + uniq;
    document.getElementById('img-temperature').src 
      = gaiaDate.strftime(t, '%Y/%m/' + site + '_temp_%Y%m%d.png') + uniq;
    document.getElementById('img-voltage').src 
      = gaiaDate.strftime(t, '%Y/%m/' + site + '_voltage_%Y%m%d.png') + uniq;
    document.getElementById('div-site-plots').style.visibility = 'visible';
    document.getElementById('div-stackplot').style.visibility = 'hidden';
  }
  return true;
};


function loadRollingPlots() {
  cancelReloadToday();
  
  if (reloadRollingID === null)
    // Set timer to reload the rolling plots
    reloadRollingID = window.setInterval(loadRollingPlots, reloadInterval_ms);
  
  var urlParts = window.location.pathname.split('/');
  var site = urlParts[urlParts.length - 2];
  var uniq = '?' + Date.now();

  if (site == 'stackplots') {
    document.getElementById('img-stackplot').src = 'rolling.png' + uniq;
    document.getElementById('div-stackplot').style.visibility = 'visible';
    document.getElementById('div-site-plots').style.visibility = 'hidden';
  }
  else {
    document.getElementById('img-magnetometer').src = 'rolling.png' + uniq;
    document.getElementById('img-temperature').src = 'rolling_temp.png' + uniq;
    document.getElementById('img-voltage').src = 'rolling_volt.png' + uniq;
    document.getElementById('div-site-plots').style.visibility = 'visible';
    document.getElementById('div-stackplot').style.visibility = 'hidden';
  }
  
  return true;
};




