/*
 * JavaScript code to support the AuroraWatchNet summary browser.
 *
 */

var reloadInterval_ms = 3 * 60 * 1000;
var reloadRollingID = null;
var reloadTodayID = null;

// Current network and site (have flexibility to select by JS later)
var network = null;
var site = null;

var imgIds = ['magnetometer', 'temperature', 'humidity',
	      'voltage', 'stackplot'];

// Format strings for the various sites
var siteDetails = {
 'aurorawatchnet': {
  // 'stackplots': {
  //   'stackplot': '%Y/%m/%Y%m%d.png',
  //   'rolling-stackplot': 'rolling.png',
  // },
  // initialiseSiteDetails() to do the rest
 },
 'cloudwatch': {
  'test2': {
    'temperature': '%Y/%m/test2_temp_%Y%m%d.png',
    'voltage': '%Y/%m/test2_voltage_%Y%m%d.png',
    'humidity': '%Y/%m/test2_humidity_%Y%m%d.png',
    'rolling-temperature': 'rolling_temp.png',
    'rolling-voltage': 'rolling_volt.png',
    'rolling-humidity': 'rolling_humidity.png',
  }
 }
};

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

function initialiseNetworkSite() {
  var urlParts = window.location.pathname.split('/');
  network = urlParts[urlParts.length - 3];
  site = urlParts[urlParts.length - 2];
}

function initialiseSiteDetails() {
  initialiseNetworkSite()
    
  var sites = ['lan1', 'lan3', 'metoffice1',
	       'bra1', 'san1', 'tob1', 'whi1', 'alt1',
	       'mal1', 'ash1', 'pel1', 'bre1', 'can1'];
  for (var i = 0; i < sites.length; ++i)
    siteDetails.aurorawatchnet[sites[i]] = {
    'magnetometer': '%Y/%m/' + sites[i] + '_%Y%m%d.png',
    'temperature': '%Y/%m/' + sites[i] + '_temp_%Y%m%d.png',
    'voltage': '%Y/%m/' + sites[i] + '_voltage_%Y%m%d.png',
    'rolling-magnetometer': 'rolling.png',
    'rolling-temperature': 'rolling_temp.png',
    'rolling-voltage': 'rolling_volt.png',
    };
}

// Initialise the webpage. Do this only after the webpage which
// included gaia_viewer.js has finished loading.
function bodyOnLoad() {
  initialiseSiteDetails();
  
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

  
  // var urlParts = window.location.pathname.split('/');
  // var site = urlParts[urlParts.length - 2];
  if (site == 'stackplots') {
    //var fstr = siteDetails[network][site][s];
    document.getElementById('img-stackplot').src 
      = gaiaDate.strftime(t, '%Y/%m/%Y%m%d.png') + uniq;
    //document.getElementById('div-stackplot').style.visibility = 'visible';
    //document.getElementById('div-site-plots').style.visibility = 'hidden';
  }
  else {
    for (var i = 0; i < imgIds.length; ++i) {
      var s = imgIds[i];
      var fstr = siteDetails[network][site][s];
      var elem = document.getElementById('img-' + s);
      if (elem == null)
	continue;
      
      if (typeof fstr == 'undefined') 
	elem.style.visibility = 'hidden'; // No such img for site
      else {
	elem.src = gaiaDate.strftime(t, fstr) + uniq;
	elem.style.visibility = 'visible';
      }
	
    }
    //document.getElementById('div-site-plots').style.visibility = 'visible';
    //document.getElementById('div-stackplot').style.visibility = 'hidden';
  }

  if (site == 'stackplots') {
    document.getElementById('div-stackplot').style.visibility = 'visible';
    document.getElementById('div-site-plots').style.visibility = 'hidden';
  }
  else {
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
  
  //var urlParts = window.location.pathname.split('/');
  //var site = urlParts[urlParts.length - 2];
  var uniq = '?' + Date.now();

  if (site == 'stackplots') {
    //var url = siteDetails[network][site]['rolling-' + site];
    var url = 'rolling.png';
    document.getElementById('img-stackplot').src = url + uniq;
    document.getElementById('div-stackplot').style.visibility = 'visible';
    document.getElementById('div-site-plots').style.visibility = 'hidden';
  }
  else {
    for (var i = 0; i < imgIds.length; ++i) {
      var s = imgIds[i];
      var url = siteDetails[network][site]['rolling-' + s];
      var elem = document.getElementById('img-' + s);
      if (elem == null)
	continue;
      if (typeof url == 'undefined')
	elem.style.visibility = 'hidden'; // No such img for site
      else {
	elem.src = url + uniq;
	elem.style.visibility = 'visible';
      }
	
    }
     
    document.getElementById('div-site-plots').style.visibility = 'visible';
    document.getElementById('div-stackplot').style.visibility = 'hidden';
  }
  
  return true;
};




