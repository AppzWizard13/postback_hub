$(function () {
    // Fetch the raw JSON string from the script tag
    var scriptTag = document.getElementById('positions-data'); 
    var data_set = scriptTag ? scriptTag.textContent : ""; // Get the content of the script tag if it exists
    // Retrieve series data from the DOM element and parse it as JSON
    // Retrieve series data from the DOM element and parse it as JSON
    var breakup_seriesTag = document.getElementById('breakup_series');
    var breakup_seriesdata = breakup_seriesTag ? breakup_seriesTag.textContent : "";
    var hourly_status_dataTag = document.getElementById('hourly_status_data');
    var hourly_status_data = hourly_status_dataTag ? hourly_status_dataTag.textContent : "";
    var daily_status_dataTag = document.getElementById('daily_status_data');
    var daily_status_data = daily_status_dataTag ? daily_status_dataTag.textContent : "";

    try {
      // Parse the JSON data and round each number
      var parsedSeriesData = JSON.parse(breakup_seriesdata);
      var breakup_series = parsedSeriesData.map(num => Math.round(num));
    
      var colors = [
        "#0d41d9", // First color - Blue (default)
        breakup_series[1] > 0 ? "#32df2d" : (breakup_series[1] < 0 ? "#ff0000" : "#3569ff"), // Green if positive, Red if negative, Blue if zero
        "#fff47d" // Third color - Orange (default)
      ];

      // Check if the second value is negative and make it positive if so
      if (breakup_series[1] < 0) {
        breakup_series[1] = Math.abs(breakup_series[1]);
      }

      // Suppose hourly_status_data is a comma-separated string of numbers, e.g., "-10, 20, -30"
      var hourly_status_data = hourly_status_dataTag ? hourly_status_dataTag.textContent : "";

      // Convert to an array of positive numbers
      var hourly_adjusted_profit_list = hourly_status_data
        .split(',')  // Split by commas to create an array
        .map(function(value) {
          // Convert each item to a number, and use Math.abs() to ensure positivity
          var number = parseFloat(value.trim());
          return isNaN(number) ? 0 : Math.abs(number); // Default to 0 if conversion fails
        });

        console.log("Adjusted profit list Hourly :", hourly_adjusted_profit_list); // Logs the list 

      // Suppose hourly_status_data is a comma-separated string of numbers, e.g., "-10, 20, -30"
      var daily_status_data = daily_status_dataTag ? daily_status_dataTag.textContent : "";

      // Convert to an array of positive numbers
      var daily_adjusted_profit_list = daily_status_data
        .split(',')  // Split by commas to create an array
        .map(function(value) {
          // Convert each item to a number, and use Math.abs() to ensure positivity
          var number = parseFloat(value.trim());
          return isNaN(number) ? 0 : Math.abs(number); // Default to 0 if conversion fails
        });
      console.log("Adjusted profit list Daily :", daily_adjusted_profit_list); // Logs the list 

    
    } catch (e) {
      console.error("Failed to parse breakup_seriesdata as JSON:", e);
      var breakup_series = [0, 0, 0]; // Default values if parsing fails
      var colors = ["#0d41d9", "#ff0000", "#fff47d"]; // Default color scheme
    }
    

    // Retrieve labels data from the DOM element and parse it as JSON
    var breakup_labelsTag = document.getElementById('breakup_labels');
    var breakup_labelsdata = breakup_labelsTag ? breakup_labelsTag.textContent : "";

    // Convert single quotes to double quotes if necessary
    breakup_labelsdata = breakup_labelsdata.replace(/'/g, '"');

    try {
      var breakup_labels = JSON.parse(breakup_labelsdata);
    } catch (e) {
      console.error("Failed to parse breakup_labelsdata as JSON:", e);
      var breakup_labels = ["Label1", "Label2", "Label3"]; // Default labels if parsing fails
    }

    // Initialize positions array
    var positions = [];

    // Check if data_set has content
    if (!data_set || data_set.trim() === "") {
        console.log('No data found in Raw Data');
    } else {
        try {
            // Parse JSON string to JavaScript object
            positions = JSON.parse(data_set);
            console.log('Parsed Positions:', positions); // Log the parsed JavaScript object
        } catch (e) {
            console.error('Error parsing JSON data:', e); // Log error if JSON parsing fails
        }
    }

    // Remove the script tag from the DOM if it exists
    if (scriptTag) {
        scriptTag.remove();
    }

    // Variables to hold categories (trading symbols), earnings, and expenses
    var categories = [];
    var earnings = [];
    var expenses = [];
    var chart_earning = [];

    let positiveEarningsSum = 0;






    // Process positions to populate categories, earnings, and expenses
    if (positions.length > 0) {
        positions.forEach(function(position) {
            categories.push(position.tradingSymbol);  // Add trading symbol to categories
              chart_earning.push(position.realizedProfit);
              chart_earning.push(0);
            // If realizedProfit is positive, add to earnings; otherwise, add to expenses
            if (position.realizedProfit > 0) {
                earnings.push(position.realizedProfit);
                expenses.push(0);  // No expense for positive profit
            } else {
                earnings.push(0);  // No earnings for negative profit
                expenses.push(Math.abs(position.realizedProfit));  // Convert negative to positive for expense
            }
        });
    } else {
        // Default values if no positions data is available
        categories = ["Default Symbol"];
        earnings = [0];
        expenses = [0];
    }
    var colour_selector = 0 
    // Iterate through chart_earning to sum positive values
    chart_earning.forEach(function(value) {
      if (value > 0) {
            positiveEarningsSum += value;
            colour_selector += value;
        }
        else{
          colour_selector += value;
        }
      
      }
    );

    let chart_earning1 = chart_earning

    chart_earning = chart_earning.filter(value => value !== 0);
    chart_earning.unshift(0);

    

    let chartColor = (colour_selector > 0) ? "#32df2d" : (colour_selector === 0 ? "#49BEFF" : "#ff2626"); 

    let chartColor1 = chartColor

    let chartColor2 = chartColor

    

    // =====================================
    // Profit Chart
    // =====================================
    var chartOptions = {
        series: [
            { name: "Profit of Position", data: earnings },
            { name: "Loss of Position", data: expenses },
        ],

        chart: {
            type: "bar",
            height: 525,
            offsetX: -15,
            toolbar: { show: true },
            foreColor: "#000000d9",
            fontFamily: 'inherit',
            sparkline: { enabled: false },
        },

        colors: ["#32df2d", "#FF0000"],

        plotOptions: {
            bar: {
                horizontal: false,
                columnWidth: "35%",
                borderRadius: [6],
                borderRadiusApplication: 'end',
                borderRadiusWhenStacked: 'all'
            },
        },
        markers: { size: 0 },

        dataLabels: {
            enabled: true,
        },

        legend: {
          show: true,
          labels: {
              colors: '#FFFFFF',  // Set the legend label color to white
              useSeriesColors: false  // Ensure it doesn't use the series colors
          }
      },
      

        grid: {
            borderColor: "rgba(0,0,0,0.1)",
            strokeDashArray: 3,
            xaxis: {
                lines: {
                    show: false,
                },
            },
        },

        xaxis: {
          type: "category",
          categories: categories,  // Dynamic trading symbols
          labels: {
              style: {
                  colors: '#FFFFFF',         // Set the label color to white
                  fontSize: '10px',            // Adjust font size as needed
              }
          }
      },
        

        yaxis: {
            show: true,
            min: 0,
            max: Math.max(...earnings.concat(expenses)) || 10,  // Dynamically adjust the max value or use default
            tickAmount: 4,
            labels: {
                style: {  colors: '#FFFFFF',         // Set the label color to white, 
                cssClass: "grey--text lighten-2--text fill-color", },
            },
        },
        stroke: {
            show: true,
            width: 3,
            lineCap: "butt",
            colors: ["transparent"],
        },

        tooltip: { theme: "dark" },

        responsive: [
            {
                breakpoint: 600,
                options: {
                    plotOptions: {
                        bar: {
                            borderRadius: 3,
                        }
                    },
                }
            }
        ]
    };

    var chart = new ApexCharts(document.querySelector("#chart"), chartOptions);
    chart.render();

// =====================================
// Performance Overview - Daily
// =====================================
var dailyperformanceOverview = {
  chart: {
    id: "dailyperformanceoverview",
    type: "area",
    height: "100%",
    width: "100%",
    sparkline: {
      enabled: true,
    },
    group: "sparklines",
    fontFamily: "'Plus Jakarta Sans', sans-serif",
    foreColor: "#adb0bb",
  },
  series: [
    {
      name: "Performance",
      color: typeof chartColor1 !== 'undefined' ? chartColor1 : "#00bfff",
      data: Array.isArray(daily_adjusted_profit_list) && daily_adjusted_profit_list.length > 0 
            ? daily_adjusted_profit_list 
            : [0], // Default value if the list is empty
    },
  ],
  stroke: {
    curve: "smooth",
    width: 2,
  },
  fill: {
    colors: ["#f3feff"],
    type: "solid",
    opacity: 0.05,
  },
  markers: {
    size: 0,
  },
  tooltip: {
    theme: "dark",
    fixed: {
      enabled: true,
      position: "right",
    },
    x: {
      show: false,
    },
  },
};

// Check if element exists before rendering the daily chart
if (document.querySelector("#dailyperformanceoverview")) {
  new ApexCharts(document.querySelector("#dailyperformanceoverview"), dailyperformanceOverview).render();
}

// =====================================
// Performance Overview - Hourly
// =====================================
var hourlyperformanceoverview = {
  chart: {
    id: "hourlyperformanceoverview",
    type: "area",
    height: "100%",
    width: "100%",
    sparkline: {
      enabled: true,
    },
    group: "sparklines",
    fontFamily: "'Plus Jakarta Sans', sans-serif",
    foreColor: "#adb0bb",
  },
  series: [
    {
      name: "Performance",
      color: typeof chartColor2 !== 'undefined' ? chartColor2 : "#ff6347",
      data: Array.isArray(hourly_adjusted_profit_list) && hourly_adjusted_profit_list.length > 0 
            ? hourly_adjusted_profit_list 
            : [0], // Default value if the list is empty
    },
  ],
  stroke: {
    curve: "smooth",
    width: 2,
  },
  fill: {
    colors: ["#f3feff"],
    type: "solid",
    opacity: 0.05,
  },
  markers: {
    size: 0,
  },
  tooltip: {
    theme: "dark",
    fixed: {
      enabled: true,
      position: "right",
    },
    x: {
      show: false,
    },
  },
};

// Check if element exists before rendering the hourly chart
if (document.querySelector("#hourlyperformanceoverview")) {
  new ApexCharts(document.querySelector("#hourlyperformanceoverview"), hourlyperformanceoverview).render();
}



    
  // =====================================
  // Earning
  // =====================================
  var earning = {
    chart: {
      id: "sparkline3",
      type: "area",
      height: 60,
      sparkline: {
        enabled: true,
      },
      group: "sparklines",
      fontFamily: "Plus Jakarta Sans', sans-serif",
      foreColor: "#adb0bb",
    },
    series: [
      {
        name: "Earnings",
        color: chartColor,
        data:chart_earning,
      },
    ],
    stroke: {
      curve: "smooth",
      width: 2,
    },
    fill: {
      colors: ["#f3feff"],
      type: "solid",
      opacity: 0.05,
    },
    

    markers: {
      size: 0,
    },
    tooltip: {
      theme: "dark",
      fixed: {
        enabled: true,
        position: "right",
      },
      x: {
        show: true,
      },
    },
  };
  new ApexCharts(document.querySelector("#earning"), earning).render();



    // =====================================
  // Breakup
  // =====================================
  var breakup = {
    color: "#adb5bd",
    series: breakup_series, // Use the parsed series data
    labels: breakup_labels, // Use the parsed labels data
    chart: {
      width: 180,
      type: "donut",
      fontFamily: "Plus Jakarta Sans', sans-serif",
      foreColor: "#adb0bb",
    },
    plotOptions: {
      pie: {
        customScale: 0.8,
        startAngle: 0,
        endAngle: 360,
        donut: {
          size: '75%',
        },
      },
    },
    stroke: {
      show: false,
    },

    dataLabels: {
      enabled: true,
    },

    legend: {
      show: true,
    },
    colors: colors,

    responsive: [
      {
        breakpoint: 3840,
        options: {
          chart: {
            width: 325,
          },
          legend: {
            position: "right",
            offsetX: 0, // Adjust this value to move the legend closer to the chart
            offsetY: 0,   // Adjust vertical alignment if needed
          },
        },
      },
    ],
    tooltip: {
      theme: "dark",
      fillSeriesColor: false,
    },
  };

  var chart = new ApexCharts(document.querySelector("#breakup"), breakup);
  chart.render();
})