import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

const API_KEY = process.env.FOOTBALL_DATA_KEY;
const BASE_URL = 'https://api.football-data.org/v4';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'X-Auth-Token': API_KEY || ''
  }
});

async function checkMatch() {
  try {
    const today = new Date();
    const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    
    console.log(`Checking matches from ${yesterday} to ${tomorrow}...`);
    const response = await api.get('/matches', { params: { dateFrom: yesterday, dateTo: tomorrow } });
    const matches = response.data.matches;
    
    console.log(`Total matches found: ${matches ? matches.length : 0}`);

    if (!matches) {
      console.log('No matches object in response.');
      return;
    }

    const arsenalMatch = matches.find((m: any) => 
      m.homeTeam.name.toLowerCase().includes('arsenal') || m.awayTeam.name.toLowerCase().includes('arsenal') ||
      m.homeTeam.name.toLowerCase().includes('atleti') || m.awayTeam.name.toLowerCase().includes('atleti')
    );

    if (arsenalMatch) {
      console.log('Match found in API:');
      console.log(`${arsenalMatch.utcDate} - ${arsenalMatch.homeTeam.name} vs ${arsenalMatch.awayTeam.name} [${arsenalMatch.status}]`);
      console.log(`Score: ${arsenalMatch.score.fullTime.home} - ${arsenalMatch.score.fullTime.away}`);
    } else {
      console.log('No Arsenal/Atletico match found in API in this range.');
      console.log('Listing some matches found:');
      matches.slice(0, 10).forEach((m: any) => console.log(`${m.utcDate}: ${m.homeTeam.name} vs ${m.awayTeam.name}`));
    }
  } catch (error: any) {
    console.error('API Check failed:', error.message);
    if (error.response) {
      console.error('Response data:', error.response.data);
    }
  }
}

checkMatch();
