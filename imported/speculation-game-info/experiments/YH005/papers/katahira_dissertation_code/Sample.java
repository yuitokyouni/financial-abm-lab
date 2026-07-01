// Reference implementation of the Speculation Game reproduced from the
// appendix of K. Katahira's Ph.D. dissertation. Line numbers and page
// numbers from the PDF have been stripped and long lines re-flowed;
// otherwise the code is unchanged. Used as the ground truth against which
// YH005 (per-agent + vectorized numpy) and YH006 (PAMS LOB) implementations
// are compared.

package sample;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;

public class Sample {
    public static void main(String[] args) {
        int iteration = 50000;               // The total time steps
        int N = 1000;                        // The number of players
        int M = 5;                           // Memory
        int S = 2;                           // The number of strategies
        int B = 9;                           // Board lot amount
        double C = 3;                        // Cognitive threshold
        int pattern = 0;                     // The number of signal patterns
        int history = 0;                     // Correspond to H(t)
        int move = 0;                        // Quantized price movement
        int cognitivePrice = 0;              // Initially zero
        double marketPrice = 100;            // Initially hundred
        double preMarketPrice = marketPrice; // Previous market price
        double deltaP = 0;                   // Market price change
        double r = 0;                        // Market return

        // Prepare initial history
        pattern = (int) Math.pow(5, M);
        history = (int) (Math.random() * pattern);

        // Generate players
        Player[] players = new Player[N];
        for (int i = 0; i < players.length; i++) {
            players[i] = new Player(S, B, pattern);
        }

        // Create an output file
        CSVFileWrite.output();

        // Start the game
        for (int t = 0; t < iteration; t++) {
            int sell = 0; // Store sell quantities
            int buy = 0;  // Store buy quantities

            // Count sell and buy quantities for all players
            for (int i = 0; i < players.length; i++) {
                // Select an action
                switch (players[i].decision(S, B, history)) {
                    case 0: // Sell
                        // Add ordered quantities
                        sell += players[i].orderQuantity();
                        break;
                    case 2: // Buy
                        buy += players[i].orderQuantity();
                        break;
                }
            }

            // Calculate the market price change
            deltaP = (double) (buy - sell) / N;

            // Decide the quantized price movement
            if (deltaP < -C) {
                move = 0; // Largely down
            } else if (deltaP < 0) {
                move = 1; // Down
            } else if (deltaP > C) {
                move = 4; // Largely up
            } else if (deltaP > 0) {
                move = 3; // Up
            } else {
                move = 2; // Stay
            }

            // Update the cognitive price
            cognitivePrice += move - 2;

            // Update the history
            history = (history * 5) % pattern + move;

            // Find the market return
            marketPrice += deltaP;
            r = Math.log(marketPrice) - Math.log(preMarketPrice);

            // Store the previous market price
            preMarketPrice = marketPrice;

            for (int i = 0; i < players.length; i++) {
                // Store opening cognitive price
                players[i].openPrices(S, cognitivePrice);

                // Update status
                players[i].update(S, B, cognitivePrice);

                // If alternation requires
                if (players[i].callAlter() == true) {
                    // Replace the player
                    players[i].replace(S, B, pattern);
                }
            }

            // Output data
            CSVFileWrite.output(r);
        }

        System.out.println("Simulation ended.");
    }
}

class Player {
    private boolean alter = false;     // Flag for alternation
    private boolean switched = false;  // Flag for switch of strategies
    private boolean[] settles;         // Flag for settlements
    private int wealth = 0;            // Market wealth
    private int use = 0;               // Strategy number in use
    private int quantity = 0;          // Store ordered quantity
    private int tradePeriod = 0;       // Store trading period of strategy in use
    private int idlePeriod = 0;        // Store idling period of strategy in use
    private int idle = 0;              // Count idling length
    private int[] openPositions;       // Store opening positions
    private int[] ongoings;            // Count trading length (+1)
    private int[][] recommends;        // Store recommended actions of strategies
    private int[] gains;               // Accumulated strategy gains
    private int[] openPrices;          // Store opening cognitive prices

    // A constructor to generate a player
    public Player(int s, int b, int pattern) {
        // Prepare arrays
        settles = new boolean[s];
        openPositions = new int[s];
        ongoings = new int[s];
        recommends = new int[s][pattern];
        gains = new int[s];
        openPrices = new int[s];

        // Distribute strategies
        for (int j = 0; j < s; j++) {
            for (int k = 0; k < pattern; k++) {
                // Generate a recommended action randomly
                recommends[j][k] = (int) (Math.random() * 3);
            }

            // Initialize
            settles[j] = false;
            openPositions[j] = 0;
            ongoings[j] = 0;
            gains[j] = 0;
            openPrices[j] = 0;
        }

        // Distribute the market wealth
        wealth = b + (int) (Math.random() * 100);
    }

    // Decision making
    public int decision(int s, int b, int history) {
        int action = 0; // Store a selected action
        for (int j = 0; j < s; j++) {
            int select = recommends[j][history];
            if (ongoings[j] > 0) { // If the trade is ongoing
                ongoings[j]++;
                if (select != 1 && select != openPositions[j]) {
                    if (j == use) {
                        tradePeriod = ongoings[j] - 1;
                    }
                    settles[j] = true;
                    ongoings[j] = 0;
                } else { // If the position can not be closed
                    if (select != 1) {
                        select = 1;
                    }
                }
            } else if (select != 1) { // If select is not hold (idle)
                // Begin a trade
                ongoings[j]++;
                openPositions[j] = select;
                if (j == use) {
                    // Decide order quantity
                    quantity = wealth / b;
                    idlePeriod = idle;
                    idle = 0;
                }
            } else {
                if (j == use) {
                    idle++;
                }
            }

            // If this strategy is in use
            if (j == use) {
                action = select;
            }
        }

        return action; // Return the selected action
    }

    // Call the ordered quantity
    public int orderQuantity() {
        return quantity;
    }

    // Store the opening cognitive prices
    public void openPrices(int s, int price) {
        for (int j = 0; j < s; j++) {
            if (ongoings[j] == 1) { // If a trade is just started
                openPrices[j] = price;
            }
        }
    }

    // Update status
    public void update(int s, int b, int price) {
        boolean review = false;  // Flag for the review of strategies
        int strategyGain = 0;    // Capital gain in a round-trip trade

        // Settle differences
        for (int j = 0; j < s; j++) {
            if (settles[j] == true) { // If the settlement needs
                // Selling price - buying price
                strategyGain = (openPositions[j] - 1) * (price - openPrices[j]);

                // Update the accumulated strategy gain
                gains[j] += strategyGain;
                if (j == use) { // If this strategy is in use
                    // (Convert strategy gain &) update the market wealth
                    wealth += quantity * strategyGain;

                    if (wealth < b) { // If the market wealth is scarce
                        alter = true; // Alter the player
                    } else {
                        review = true;
                    }
                }

                // Initialize
                settles[j] = false;
            }
        }

        // If the strategies need be reviewed
        if (review == true) {
            int preUse = use; // Remember the strategy number just in use

            // Decide the best strategy
            for (int j = 0; j < s; j++) {
                if (use != j) {
                    if (gains[use] == gains[j]) {
                        if (Math.random() < 0.5) { // Decide randomly
                            use = j;
                        }
                    } else if (gains[use] < gains[j]) {
                        use = j;
                    }
                }
            }

            if (use != preUse) { // If the best strategy is changed
                // Initialize in case that a virtual trade is ongoing
                ongoings[use] = 0;
                switched = true;
            }
        }
    }

    // Call the flag for alternation
    public boolean callAlter() {
        return alter;
    }

    // Generate a substitute player
    public void replace(int s, int b, int pattern) {
        for (int j = 0; j < s; j++) {
            for (int k = 0; k < pattern; k++) {
                recommends[j][k] = (int) (Math.random() * 3);
            }

            settles[j] = false;
            ongoings[j] = 0;
            gains[j] = 0;
        }

        wealth = b + (int) (Math.random() * 100);

        // Initialize
        alter = false;
        switched = false;
    }

    // Call the flag for switch of strategies
    public boolean callSwitched() {
        boolean temp = switched;
        switched = false;
        return temp;
    }

    // Call the market wealth
    public int callWealth() {
        return wealth;
    }

    // Call the trading period
    public int callTradePeriod() {
        int temp = tradePeriod;
        tradePeriod = 0;
        return temp;
    }

    // Call the idling period
    public int callIdlePeriod() {
        int temp = idlePeriod;
        idlePeriod = 0;
        return temp;
    }
}

class CSVFileWrite {
    // Create an output file
    public static void output() {
        try {
            FileWriter fw = new FileWriter("sample.csv", false);
            PrintWriter pw = new PrintWriter(new BufferedWriter(fw));

            pw.close();

        } catch (IOException ex) {
            ex.printStackTrace();
        }
    }

    // Record data
    public static void output(double r) {
        try {
            FileWriter fw = new FileWriter("sample.csv", true);
            PrintWriter pw = new PrintWriter(new BufferedWriter(fw));

            pw.print(r);
            pw.println(",");
            pw.close();

        } catch (IOException ex) {
            ex.printStackTrace();
        }
    }
}
