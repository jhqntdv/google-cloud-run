import numpy as np
from scipy.optimize import minimize, Bounds
from scipy.stats import norm

def run_cca(metric, s0_target, voleq_target, tev0_target, rfr, t, nsim=1e5, seed=42):
    np.random.seed(seed)

    if t <= 0.01:
        t = 0.00001

    # metric column indices
    metric_id = {
        'shares': 1,
        'is_time': 2,
        'strike': 3,
        'v_cnt': 4,
        'vstart': 5,
        'vmid': 6,
        'vend': 7,
        'vstart_perc': 8,
        'vmid_perc': 9,
        'vend_perc': 10,
        'groups': 11,
        'is_cliff': 12,
        'Note': 13,
        'cm': 1  # common stock index
    }

    validation = validate_metric(metric, metric_id)
    if not validation['status']:
        result = {'status': False, 'message': validation['message']}
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

    # up and reval
    st_bump = mc(x_opt[0] * 1.005, x_opt[1], rfr, t, dz)
    vals_bump = calibration_v(st_bump, metric, each_shares, rfr, t, ncomps, nsim, metric_id, flag_output)

    # delta and spec volatility
    vals['delta'] = (vals_bump['fair_value_per_share'] - vals['fair_value_per_share']) * each_shares / (vals_bump['tev0'] - vals['tev0'])
    vals['spec_vol'] = voleq_target * vals['delta'] * vals['tev0'] / (vals['fair_value_per_share'] * each_shares)
    vals['spec_vol'][metric_id['cm'] - 1] = x_opt[1]
    vals['spec_vol'] = np.round(vals['spec_vol'] / 0.025) * 0.025 # round to nearest 0.025

    # dlom
    sigma2t = t * vals['spec_vol']**2 / 2
    v2t = sigma2t + np.log(2 * (np.exp(sigma2t) - sigma2t - 1)) - 2 * np.log(np.exp(sigma2t) - 1)
    vt = np.sqrt(v2t)
    d = vt / 2
    q = 0.0
    vals['dlom'] = np.round(np.exp(-q*t) * (2 * norm.cdf(d) - 1) / 0.025) * 0.025 # round to nearest 0.025

    # calculate post-dlom fair value
    vals['fair_value_per_share_post_dlom'] = vals['fair_value_per_share'] * (1 - vals['dlom'])

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
    vmids = metric[:, metric_id['vmid'] - 1]
    vends = metric[:, metric_id['vend'] - 1]
    is_time_flags = metric[:, metric_id['is_time'] - 1]
    v_cnts = metric[:, metric_id['v_cnt'] - 1]

    # 1. First row should be common (with strike 0 and is_time 1)
    common_idx = metric_id['cm'] - 1
    first_row_strike_valid = strikes[common_idx] == 0
    first_row_is_time_valid = is_time_flags[common_idx] == 1
    if not first_row_strike_valid:
        return {'status': False, 'message': 'Common row strike must be 0'}
    if not first_row_is_time_valid:
        return {'status': False, 'message': 'Common row is_time must be 1'}
    
    # 2. If is_time is 1, v_cnt should be 0, vstart, vmid, vend should be -1
    is_time_1_mask = is_time_flags == 1
    is_time_1_count = np.sum(is_time_1_mask)
    
    if is_time_1_count > 0:
        v_cnt_valid = np.all(v_cnts[is_time_1_mask] == 0)
        vstart_valid = np.all(vstarts[is_time_1_mask] == -1)
        vmid_valid = np.all(vmids[is_time_1_mask] == -1)
        vend_valid = np.all(vends[is_time_1_mask] == -1)
        
        if not v_cnt_valid:
            invalid_rows = np.where(is_time_1_mask & (v_cnts != 0))[0]
            return {'status': False, 'message': f'v_cnt must be 0 when is_time=1. Rows: {invalid_rows}'}
        
        if not vstart_valid:
            invalid_rows = np.where(is_time_1_mask & (vstarts != -1))[0]
            return {'status': False, 'message': f'vstart must be -1 when is_time=1. Rows: {invalid_rows}'}
        
        if not vmid_valid:
            invalid_rows = np.where(is_time_1_mask & (vmids != -1))[0]
            return {'status': False, 'message': f'vmid must be -1 when is_time=1. Rows: {invalid_rows}'}
        
        if not vend_valid:
            invalid_rows = np.where(is_time_1_mask & (vends != -1))[0]
            return {'status': False, 'message': f'vend must be -1 when is_time=1. Rows: {invalid_rows}'}
    
    # 3. strike should be non-negative
    if np.any(strikes < 0):
        invalid_rows = np.where(strikes < 0)[0]
        return {'status': False, 'message': f'strike must be non-negative. Rows: {invalid_rows}'}

    return {'status': True, 'message': ''}
    
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
    vmids = metric[:, metric_id['vmid'] - 1]
    vends = metric[:, metric_id['vend'] - 1]

    vstarts_perc = metric[:, metric_id['vstart_perc'] - 1]
    vmids_perc = metric[:, metric_id['vmid_perc'] - 1]
    vends_perc = metric[:, metric_id['vend_perc'] - 1]

    is_time = metric[:, metric_id['is_time'] - 1].astype(bool)
    v_cnts = metric[:, metric_id['v_cnt'] - 1]
    is_cliff = metric[:, metric_id['is_cliff'] - 1].astype(bool)

    payoff_per_share = np.maximum(st[:, np.newaxis] - strikes, 0) # Reshape st to (nsim, 1) for broadcasting

    vest_array = np.ones((nsim, ncomps))
    not_time = ~is_time

    step_vest_idx = np.where(not_time & (v_cnts == 1))[0]
    if step_vest_idx.size > 0:
        vest_array[:, step_vest_idx] = (st[:, np.newaxis] >= vstarts[step_vest_idx]).astype(int)

    ramp_vest_idx = np.where(not_time & (v_cnts == 2) & ~is_cliff)[0]
    if ramp_vest_idx.size > 0:
        ramp_vest_idx = ramp_vest_idx[~is_cliff[ramp_vest_idx]]
        denom = (vends[ramp_vest_idx] - vstarts[ramp_vest_idx])
        vested_ramp = np.maximum(0, np.minimum(1, (st[:, np.newaxis] - vstarts[ramp_vest_idx]) / denom))
        vest_array[:, ramp_vest_idx] = vested_ramp
    
    ramp_vest_3tranches_idx = np.where(not_time & (v_cnts == 3) & ~is_cliff)[0]
    if ramp_vest_3tranches_idx.size > 0:
        x0 = vstarts[ramp_vest_3tranches_idx]
        x1 = vmids[ramp_vest_3tranches_idx]
        x2 = vends[ramp_vest_3tranches_idx]
        
        y0 = vstarts_perc[ramp_vest_3tranches_idx]
        y1 = vmids_perc[ramp_vest_3tranches_idx]
        y2 = vends_perc[ramp_vest_3tranches_idx]
        
        x = st[:, np.newaxis]  # (nsim, 1)
        
        slope1 = (y1 - y0) / (x1 - x0)
        seg1 = y0 + slope1 * (x - x0)
        
        slope2 = (y2 - y1) / (x2 - x1)
        seg2 = y1 + slope2 * (x - x1)
        
        vested_3tranches = np.where((x >= x0) & (x < x1), seg1,
                                    np.where((x >= x1) & (x < x2), seg2,
                                    np.where(x >= x2, y2, y0)))
        
        vest_array[:, ramp_vest_3tranches_idx] = np.clip(vested_3tranches, 0, 1)

    cliff_vest_idx = np.where(not_time & (v_cnts == 2) & is_cliff)[0]
    if cliff_vest_idx.size > 0:
        x0 = vstarts[cliff_vest_idx]
        x2 = vends[cliff_vest_idx]
        
        y0 = vstarts_perc[cliff_vest_idx]
        y2 = vends_perc[cliff_vest_idx]
        
        vested_cliff = np.where(x >= x2, y2,
                        np.where(x >= x0, y0, 0))
        
        vest_array[:, cliff_vest_idx] = np.clip(vested_cliff, 0, 1)


    cliff_vest_idx_3tranche = np.where(not_time & (v_cnts == 3) & is_cliff)[0]
    if cliff_vest_idx_3tranche.size > 0:
        x0 = vstarts[cliff_vest_idx_3tranche]
        x1 = vmids[cliff_vest_idx_3tranche]
        x2 = vends[cliff_vest_idx_3tranche]
        
        y0 = vstarts_perc[cliff_vest_idx_3tranche]
        y1 = vmids_perc[cliff_vest_idx_3tranche]
        y2 = vends_perc[cliff_vest_idx_3tranche]
        
        vested_cliff = np.where(x >= x2, y2,
                        np.where(x >= x1, y1,
                        np.where(x >= x0, y0, 0)))
        
        vest_array[:, cliff_vest_idx_3tranche] = np.clip(vested_cliff, 0, 1)

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
        vals['intrinsic_value_per_share'] = np.maximum(vals['s0'] - strikes, 0) * np.mean(vest_array, axis=0) * np.exp(-rfr * t)
    return vals

def mc(s0, vol, rfr, t, dz):
    st = s0 * np.exp((rfr - 0.5 * vol**2) * t + np.sqrt(t) * vol * dz)
    return st