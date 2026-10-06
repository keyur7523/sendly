// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {DemoUSD} from "../src/DemoUSD.sol";

/// Deploys DemoUSD with the broadcasting account as owner.
/// Usage (see README): forge script script/Deploy.s.sol --rpc-url monad_testnet --account <keystore> --broadcast
contract Deploy is Script {
    function run() external returns (DemoUSD token) {
        vm.startBroadcast();
        token = new DemoUSD(msg.sender);
        vm.stopBroadcast();
        console.log("DemoUSD deployed at", address(token));
        console.log("Owner", msg.sender);
    }
}
