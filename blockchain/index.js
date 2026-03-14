const express = require('express');
const Web3 = require('web3').default;
const cors = require('cors');
require("dotenv").config()
const { PinataSDK } = require("pinata-web3")
const multer = require('multer');
const fs = require("fs")
const axios = require('axios');

const AI_VERIFIER_URL = "http://localhost:8002/verify-report";
const SCORE_THRESHOLD = 40;
const QUARANTINE_FILE = "./quarantine_reports.json";

const app = express();
app.use(cors());
app.use(express.json());

const pinata = new PinataSDK({
    pinataJwt: process.env.PINATA_JWT,
    pinataGateway: process.env.GATEWAY_URL
})

// Connect to Polygon node Infura
const web3 = new Web3(process.env.RPC_URL || 'https://ethereum-sepolia-rpc.publicnode.com');
const contractAddress = process.env.CONTRACT_ADDRESS;
const contractABI = require('./DrugUseReportingABI.json'); // Updated ABI
const contract = new web3.eth.Contract(contractABI, contractAddress);

const privateKey = process.env.WALLET_PRIVATEKEY;
const account = web3.eth.accounts.privateKeyToAccount(privateKey);
web3.eth.accounts.wallet.add(account);


const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, './uploads'); // Store files in the 'uploads' directory
    },
    filename: (req, file, cb) => {
        cb(null, Date.now() + '-' + file.originalname); // Rename file with timestamp
    }
});

// Initialize multer upload
const uploadMiddleware = multer({ storage: storage });

app.get('/', (req, res) => {
    res.send("AnonSentra Backend Operational")
});

async function verifyWithAI(location, description, imageUrl = null) {
    try {
        const response = await axios.post(AI_VERIFIER_URL, {
            location,
            description,
            image_url: imageUrl,
            timestamp: new Date().toISOString()
        });
        return response.data;
    } catch (error) {
        console.error("AI Verification failed, falling back to Needs Review:", error.message);
        return { legitimacy_score: 50, classification: "needs_review", reasoning: ["AI service unreachable"] };
    }
}

function quarantineReport(reportData) {
    let reports = [];
    if (fs.existsSync(QUARANTINE_FILE)) {
        reports = JSON.parse(fs.readFileSync(QUARANTINE_FILE));
    }
    reports.push({ ...reportData, quarantinedAt: new Date().toISOString() });
    fs.writeFileSync(QUARANTINE_FILE, JSON.stringify(reports, null, 2));
}

// API to upload report
app.post('/upload-report', async (req, res) => {
    const { textData, location } = req.body;
    try {
        const aiResult = await verifyWithAI(location || "Unknown", textData);
        
        if (aiResult.legitimacy_score < SCORE_THRESHOLD) {
            quarantineReport({ textData, location, aiResult });
            return res.status(200).json({ 
                success: false, 
                message: "Report quarantined due to low legitimacy score", 
                aiResult 
            });
        }

        const gasPrice = await web3.eth.getGasPrice();
        await contract.methods.addReport(textData).send({ from: account.address, gas: 500000, gasPrice: gasPrice });
        res.status(200).json({ success: true, aiResult });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.post('/upload-link-and-report', async (req, res) => {
    const { textData, url, location } = req.body;
    try {
        const aiResult = await verifyWithAI(location || "Unknown", textData);

        if (aiResult.legitimacy_score < SCORE_THRESHOLD) {
            quarantineReport({ textData, url, location, aiResult });
            return res.status(200).json({ 
                success: false, 
                message: "Report quarantined due to low legitimacy score", 
                aiResult 
            });
        }

        const gasPrice = await web3.eth.getGasPrice();
        await contract.methods.addReport(textData, url).send({ from: account.address, gas: 500000, gasPrice: gasPrice });
        res.status(200).json({ success: true, aiResult });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.post('/upload-image-and-report', uploadMiddleware.single('image'), async (req, res) => {
    try {
        const { textData, location } = req.body;
        const file = req.file;

        if (!file) {
            return res.status(400).json({ success: false, error: 'No file uploaded' });
        }

        // 1. Temporary upload to IPFS for AI visibility
        const randomSuffix = crypto.randomUUID().toString('hex');
        const newFileName = `${file.originalname.split('.')[0]}_${randomSuffix}.${file.originalname.split('.').pop()}`;
        const fileContent = fs.readFileSync(file.path);
        const blob = new Blob([fileContent]);
        const pinataFile = new File([blob], newFileName, { type: file.mimetype });
        const pinataResponse = await pinata.upload.file(pinataFile);
        const imageUrl = `https://${process.env.GATEWAY_URL}/ipfs/${pinataResponse.IpfsHash}`;

        // 2. AI Verification with Multimodal support
        const aiResult = await verifyWithAI(location || "Unknown", textData, imageUrl);

        if (aiResult.legitimacy_score < SCORE_THRESHOLD) {
            // Note: We leave the image on IPFS but quarantine the metadata
            quarantineReport({ textData, location, imageUrl, aiResult });
            fs.unlinkSync(file.path); // Clean up disk
            return res.status(200).json({ 
                success: false, 
                message: "Report quarantined due to low legitimacy score", 
                aiResult 
            });
        }

        // 3. Final Blockchain Submission
        const gasPrice = await web3.eth.getGasPrice();
        await contract.methods.addReport(textData, imageUrl).send({
            from: account.address,
            gas: 500000,
            gasPrice: gasPrice
        });

        fs.unlinkSync(file.path);
        res.status(200).json({ success: true, message: 'Report and image uploaded successfully', imageUrl, aiResult });
    } catch (error) {
        console.error(error);
        if (req.file) fs.unlinkSync(req.file.path);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/reports', async (req, res) => {
    try {
        // Verify ownership
        const ownerAddress = await contract.methods.owner().call();
        if (ownerAddress.toLowerCase() !== account.address.toLowerCase()) {
            return res.status(403).json({ error: 'Unauthorized: Not the contract owner' });
        }

        // Call getReports() function
        const reports = await contract.methods.getReports().call({ from: account.address });
        
        // Transform the reports into a more readable format
        const formattedReports = reports.map(report => ({
            textData: report.textData,
            ipfsHash: report.ipfsHash
        }));

        res.json(formattedReports);
    } catch (error) {
        console.error('Error fetching reports:', error);
        res.status(500).json({ error: 'Failed to fetch reports' });
    }
});

// Start server
app.listen(3000, () => {
    console.log('Server running on port 3000');
});