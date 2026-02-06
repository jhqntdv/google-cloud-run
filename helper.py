import numpy as np
from scipy.optimize import minimize, Bounds

def run_cca(metric, s0_target, voleq_target, tev0_target, rfr, t, nsim=1e5, seed=42):
    np.random.seed(seed)

    if t <= 0.01:
        t = 0.00001

    # metric column indices
    metric_id = {
        'shares': 1,
        'strike': 2,
        'vstart': 3,
        'vend': 4,
        'is_time': 5,
        'v_cnt': 6,
        'groups': 7,
        'is_cliff': 8,
        'cm': 1  # common stock index
    }

    if not validate_metric(metric, metric_id):
        result = {'status': False, 'message': 'metric validation failed'}
        return result

    ncomps = metric.shape[0]
    dz = np.random.randn(nsim)
    each_shares = metric[:, metric_id['shares'] - 1].flatten()

    lambda_obj = lambda x: obj(x, dz, metric, each_shares, rfr, t, s0_target, voleq_target, tev0_target, ncomps, nsim, metric_id)
    if s0_target <= 0:
        x0 = [tev0_target / each_shares[metric_id['cm'] - 1], voleq_target]
    else:
        x0 = [s0_target, voleq_target]
    bounds = Bounds([0.01, 0.05], [10**4.0, 1.00])
    linear_constraint = None # LinearConstraint([[1, 1]], [1], [3])

    res = minimize(lambda_obj, x0, method='L-BFGS-B', bounds=bounds)

    x_opt = res.x

    st = mc(x_opt[0], x_opt[1], rfr, t, dz)

    flag_output = True
    vals = calibration_v(st, metric, each_shares, rfr, t, ncomps, nsim, metric_id, flag_output)

    result = vals
    result['volcm'] = x_opt[1]
    result['iterations'] = res.nit # Number of iterations

    sim_tev_ratio_check = vals['sim_tev'] / vals['tev0']
    c1 = 1 / np.mean(np.exp(np.log(sim_tev_ratio_check))) # - exp(-rfr * t) was commented out
    c2 = np.std(np.log(sim_tev_ratio_check)) / np.sqrt(t) # - voleq_target was commented out
    result['check'] = [c1, c2, x_opt[1] / voleq_target]

    result['status'] = True
    result['message'] = 'cca completed'

    iterations_details = {
        'iterations': res.nit,              # Number of iterations
        'function_evaluations': res.nfev,   # Number of function evaluations
        'success': res.success,             # Whether optimization succeeded
        'status': res.status,               # Termination status
        'message': res.message,             # Description of the cause of termination
        'final_objective': res.fun,         # Final objective function value
        'initial_guess': x0,                # Initial guess
        'optimal_values': x_opt.tolist()    # Optimal parameter values
    }

    result['iterations_details'] = iterations_details

    return result

def validate_metric(metric, metric_id):
    strikes = metric[:, metric_id['strike'] - 1]
    vstarts = metric[:, metric_id['vstart'] - 1] 
    vends = metric[:, metric_id['vend'] - 1]
    is_time_flags = metric[:, metric_id['is_time'] - 1]
    v_cnts = metric[:, metric_id['v_cnt'] - 1]
    is_cliff_flags = metric[:, metric_id['is_cliff'] - 1]
    # 1. All values in metric should be non-negative
    all_non_negative = np.all(metric >= 0)
    if not all_non_negative:
        negative_positions = np.where(metric < 0)
        return False
    
    # 2. First row should be common (with strike 0 and is_time 1)
    first_row_strike_valid = strikes[0] == 0
    first_row_is_time_valid = is_time_flags[0] == 1
    if not first_row_strike_valid:
        return False
    if not first_row_is_time_valid:
        return False
    
    # 3. If is_time is 1, vstart and v_cnt should be 0
    is_time_1_mask = is_time_flags == 1
    is_time_1_count = np.sum(is_time_1_mask)
    
    if is_time_1_count > 0:
        vstart_valid_for_is_time_1 = np.all(vstarts[is_time_1_mask] == 0)
        v_cnt_valid_for_is_time_1 = np.all(v_cnts[is_time_1_mask] == 0)
        
        if not vstart_valid_for_is_time_1:
            invalid_vstart_rows = np.where(is_time_1_mask & (vstarts != 0))[0]
            return False
            
        if not v_cnt_valid_for_is_time_1:
            invalid_v_cnt_rows = np.where(is_time_1_mask & (v_cnts != 0))[0]
            return False
    
    # 4. If is_time is 0, v_cnt should be 1 + 1*(vend != 0)
    is_time_0_mask = is_time_flags == 0
    is_time_0_count = np.sum(is_time_0_mask)
    
    if is_time_0_count > 0:
        expected_v_cnt = 1 + (vends[is_time_0_mask] != 0).astype(int)
        actual_v_cnt = v_cnts[is_time_0_mask]
        
        v_cnt_valid_for_is_time_0 = np.all(actual_v_cnt == expected_v_cnt)
        
        if not v_cnt_valid_for_is_time_0:
            invalid_mask = actual_v_cnt != expected_v_cnt
            invalid_rows = np.where(is_time_0_mask)[0][invalid_mask]
            return False
        
    return True
    
def obj(x, dz, metric, each_shares, rfr, t, s0_target, voleq_target, tev0_target, ncomps, nsim, metric_id):
    st = mc(x[0], x[1], rfr, t, dz)

    vals = calibration_v(st, metric, each_shares, rfr, t, ncomps, nsim, metric_id, False)

    w_voleq = 1.0
    noise = w_voleq * (vals['voleq'] - voleq_target)**2

    if tev0_target > 0:
        w_s0 = 0.0
        w_tev = 1.0
        noise += w_tev * (vals['tev0'] / tev0_target - 1)**2    
    else:
        w_s0 = 1.0
        w_tev = 0.0
        noise += w_s0 * (vals['s0'] - s0_target)**2
    
    return noise

def calibration_v(st, metric, each_shares, rfr, t, ncomps, nsim, metric_id, flag_output):
    strikes = metric[:, metric_id['strike'] - 1]
    vstarts = metric[:, metric_id['vstart'] - 1]
    vends = metric[:, metric_id['vend'] - 1]
    is_time = metric[:, metric_id['is_time'] - 1].astype(bool)
    v_cnts = metric[:, metric_id['v_cnt'] - 1]
    is_cliff = metric[:, metric_id['is_cliff'] - 1].astype(bool)

    payoff_per_share = np.maximum(st[:, np.newaxis] - strikes, 0) # Reshape st to (nsim, 1) for broadcasting

    vest_array = np.ones((nsim, ncomps))
    not_time = ~is_time

    step_vest_idx = np.where(not_time & (v_cnts == 1))[0]
    if step_vest_idx.size > 0:
        vest_array[:, step_vest_idx] = (st[:, np.newaxis] >= vstarts[step_vest_idx]).astype(int)

    ramp_vest_idx = np.where(not_time & (v_cnts > 1) & ~is_cliff)[0]
    if ramp_vest_idx.size > 0:
        ramp_vest_idx = ramp_vest_idx[~is_cliff[ramp_vest_idx]]
        denom = (vends[ramp_vest_idx] - vstarts[ramp_vest_idx])
        vested_ramp = np.maximum(0, np.minimum(1, (st[:, np.newaxis] - vstarts[ramp_vest_idx]) / denom))
        vest_array[:, ramp_vest_idx] = vested_ramp
    
    cliff_vest_idx = np.where(not_time & (v_cnts > 1) & is_cliff)[0]
    if cliff_vest_idx.size > 0:
        # vmid = 0.5 * (vstarts + vends)
        # 1/3 if st exceeds vstart, 2/3 if st exceeds vmid, 100% if st exceeds vend
        vmid = 0.5 * (vstarts[cliff_vest_idx] + vends[cliff_vest_idx])
        vest_array[:, cliff_vest_idx] = (1/3) * (st[:, np.newaxis] >= vstarts[cliff_vest_idx]).astype(int) + \
                                        (1/3) * (st[:, np.newaxis] >= vmid).astype(int) + \
                                        (1/3) * (st[:, np.newaxis] >= vends[cliff_vest_idx]).astype(int)

    payoff_per_share = payoff_per_share * vest_array

    sim_tev = np.sum(payoff_per_share * each_shares, axis=1)
    avg_payoff = np.mean(payoff_per_share, axis=0)
    fair_value_per_share = avg_payoff * np.exp(-rfr * t)

    vals = {}
    vals['s0'] = fair_value_per_share[metric_id['cm'] - 1]
    vals['tev0'] = np.sum(fair_value_per_share * each_shares)
    vals['voleq'] = np.std(np.log(sim_tev / vals['tev0'])) / np.sqrt(t)

    if flag_output:
        vals['payoff_per_share'] = payoff_per_share
        vals['vest_array'] = vest_array
        vals['fair_value_per_share'] = fair_value_per_share
        vals['sim_tev'] = sim_tev
        vals['dilution'] = fair_value_per_share[metric_id['cm'] - 1] * each_shares[metric_id['cm'] - 1] / vals['tev0']
        vals['num_of_class'] = len(fair_value_per_share)
        vals['strikes'] = strikes
        vals['is_time'] = is_time
        vals['is_cliff'] = is_cliff
    return vals

def mc(s0, vol, rfr, t, dz):
    st = s0 * np.exp((rfr - 0.5 * vol**2) * t + np.sqrt(t) * vol * dz)
    return st