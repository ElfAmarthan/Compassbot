const express = require("express");
const cors = require("cors");
const app = express();
const axios = require("axios");

// Middleware setup
app.use(cors());
app.use(express.json()); // Parses JSON bodies
const path = require("path");

// Serve static files from "public" directory
app.use(express.static(path.join(__dirname, "public")));

// To store the received data in memory
let storedData = null;

// POST endpoint for receiving data
app.post("/receive-locations", (req, res) => {
  const { pickup, destination, distance, fare } = req.body || {}; // Safely handle undefined body

  if (!pickup || !destination || !distance || !fare) {
    return res.status(400).json({ error: "Missing data" });
  }

  // Store the received data for later fetching
  storedData = { pickup, destination, distance, fare };

  console.log("Received Pickup:", pickup);
  console.log("Received Destination:", destination);
  console.log("Distance:", distance);
  console.log("Fare:", fare);

  // Send a success response
  res.status(200).json({
    message: "Locations received successfully",
    pickup,
    destination,
    distance,
    fare,
  });
});

// GET endpoint for sending data to the bot
app.get("/receive-locations", (req, res) => {
  if (!storedData) {
    return res.status(404).json({ error: "No data available" });
  }

  res.status(200).json(storedData);
});

// POST endpoint for /send-locations-to-user to receive data and handle bot logic
app.post("/send-locations-to-user", (req, res) => {
  const { pickup, destination, distance, fare } = req.body;

  if (!pickup || !destination || !distance || !fare) {
    return res.status(400).json({ error: "Missing required data" });
  }

  // Handle the data received from the frontend
  console.log("Received Locations from Frontend:");
  console.log("Pickup:", pickup);
  console.log("Destination:", destination);
  console.log("Distance:", distance);
  console.log("Fare:", fare);

  // You can implement bot interaction logic here if needed
  // For example, you can send this data to the bot or handle any further processing

  // Respond back to confirm data handling
  res
    .status(200)
    .json({ message: "Locations received and processed successfully!" });
});

// POST endpoint to notify the bot
app.post("/notify-bot", (req, res) => {
  // Check if there's location data available
  if (storedData) {
    // Send the location data to the bot
    axios
      .post("http://192.168.0.107:5500/send-locations-to-user", storedData)
      .then((response) => {
        console.log("Bot notified successfully.");
        res.status(200).json({ message: "Bot notified successfully" });
      })
      .catch((error) => {
        console.error("Error notifying bot:", error);
        res.status(500).json({ error: "Failed to notify bot" });
      });
  } else {
    res.status(404).json({ error: "No location data available" });
  }
});

const LOCAL_IP = "192.168.0.107"; // Replace with your actual IP
const PORT = process.env.PORT || 5500;
app.listen(PORT, LOCAL_IP, () => {
  console.log(`Server is running on http://${LOCAL_IP}:${PORT}`);
});
